// Cliente HTTP da API. Todas as chamadas passam por aqui, então o tratamento
// de erro e o token de login ficam num lugar só.
// Os tipos abaixo espelham os schemas Pydantic do back-end (app/schemas/publico.py).

// "/api" é repassado para o back-end pelo proxy do Vite (ver vite.config.ts).
const BASE_URL = "/api";

export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

type Parametros = Record<string, string | number | boolean | undefined | null>;

function montarUrl(caminho: string, params?: Parametros): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params ?? {})) {
    if (valor !== undefined && valor !== null && valor !== "") busca.set(chave, String(valor));
  }
  const qs = busca.toString();
  return `${BASE_URL}${caminho}${qs ? `?${qs}` : ""}`;
}

// ----------------------------------------------------------------- token
// O token JWT fica no localStorage: sobrevive a recarregar a página.
// (Trade-off conhecido: um script malicioso na página conseguiria lê-lo; num
// produto real, um cookie httpOnly é mais seguro. Para o MVP, localStorage é simples e suficiente.)
const CHAVE_TOKEN = "radar_token";

export function lerToken(): string | null {
  try {
    return localStorage.getItem(CHAVE_TOKEN);
  } catch {
    return null;
  }
}

export function salvarToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CHAVE_TOKEN, token);
    else localStorage.removeItem(CHAVE_TOKEN);
  } catch {
    /* navegador sem localStorage: segue sem lembrar o login */
  }
}

// Avisado quando a API responde 401 com um token salvo (sessão expirou).
export const EVENTO_SESSAO_EXPIRADA = "radar:sessao-expirada";

async function requisitar(caminho: string, init: RequestInit & { params?: Parametros } = {}): Promise<Response> {
  const { params, headers, ...resto } = init;
  const token = lerToken();
  let resposta: Response;
  try {
    resposta = await fetch(montarUrl(caminho, params), {
      ...resto,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers },
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ErroApi(0, "Não foi possível conectar à API. Verifique se ela está no ar.");
  }
  if (!resposta.ok) {
    if (resposta.status === 401 && token) {
      salvarToken(null);
      window.dispatchEvent(new Event(EVENTO_SESSAO_EXPIRADA));
    }
    // A API devolve {"detail": "..."} com a mensagem do erro (ou uma lista, nos erros de validação)
    const corpo = await resposta.json().catch(() => null);
    const detalhe =
      typeof corpo?.detail === "string"
        ? corpo.detail
        : Array.isArray(corpo?.detail)
          ? corpo.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, "")).join(" ")
          : `Erro ${resposta.status}`;
    throw new ErroApi(resposta.status, detalhe);
  }
  return resposta;
}

export async function getJson<T>(caminho: string, params?: Parametros, signal?: AbortSignal): Promise<T> {
  return (await requisitar(caminho, { params, signal })).json() as Promise<T>;
}

export async function postJson<T>(caminho: string, corpo?: unknown): Promise<T> {
  const resposta = await requisitar(caminho, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  return resposta.json() as Promise<T>;
}

export async function deletar(caminho: string): Promise<void> {
  await requisitar(caminho, { method: "DELETE" });
}

/** Baixa um arquivo de uma rota autenticada (o link comum não mandaria o token). */
export async function baixarArquivo(caminho: string, params: Parametros, nomePadrao: string) {
  const resposta = await requisitar(caminho, { params });
  const nome = resposta.headers.get("content-disposition")?.match(/filename="(.+)"/)?.[1] ?? nomePadrao;
  const url = URL.createObjectURL(await resposta.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  link.click();
  URL.revokeObjectURL(url);
}

// ------------------------------------------------------------------ tipos

export type Periodo = { de: string; ate: string };

export type Pagina<T> = { itens: T[]; total: number; pagina: number; itens_por_pagina: number };

export type Categoria = { id: number; slug: string; nome: string; descricao: string };

export type DeputadoResumo = {
  id: number;
  nome: string;
  partido: string;
  uf: string;
  url_foto: string | null;
  em_exercicio: boolean;
  total_periodo: number;
  n_notas: number;
};

export type ValorPorCategoria = { categoria: Categoria; total: number; n_notas: number; percentual: number };
export type ValorPorMes = { ano: number; mes: number; total: number; n_notas: number };
export type FornecedorTotal = { cnpj_cpf: string | null; nome: string; total: number; n_notas: number };
export type ComparacaoUF = { uf: string; mediana_uf: number; n_deputados_uf: number; razao: number | null };
export type ResumoIA = { texto: string; periodo: string; modelo_usado: string; gerado_em: string };

export type DeputadoPerfil = {
  id: number;
  nome: string;
  nome_civil: string | null;
  partido: string;
  uf: string;
  url_foto: string | null;
  email: string | null;
  legislatura: number;
  em_exercicio: boolean;
  periodo: Periodo;
  total: number;
  n_notas: number;
  media_mensal: number;
  por_categoria: ValorPorCategoria[];
  por_mes: ValorPorMes[];
  top_fornecedores: FornecedorTotal[];
  comparacao_uf: ComparacaoUF | null;
  resumo_ia: ResumoIA | null;
  n_alertas: number;
};

export type Despesa = {
  id: number;
  ano: number;
  mes: number;
  data_documento: string | null;
  categoria: Categoria;
  fornecedor_nome: string | null;
  fornecedor_cnpj_cpf: string | null;
  tipo_documento: string | null;
  num_documento: string | null;
  valor_documento: number;
  valor_glosa: number;
  valor_liquido: number;
  url_documento: string | null;
};

export type TipoRanking = "categoria" | "uf" | "partido" | "deputado";

export type ItemRanking = {
  posicao: number;
  chave: string;
  nome: string;
  total: number;
  n_notas: number;
  n_deputados: number;
  media_por_deputado: number;
  uf: string | null;
  partido: string | null;
  url_foto: string | null;
};

export type Ranking = { tipo: TipoRanking; periodo: Periodo; itens: ItemRanking[] };

export type VisaoGeral = {
  periodo: Periodo;
  total: number;
  n_notas: number;
  n_deputados_com_gasto: number;
  media_por_deputado: number;
  n_alertas: number;
  categoria_mais_cara: ValorPorCategoria | null;
  por_categoria: ValorPorCategoria[];
  por_mes: ValorPorMes[];
  ultima_atualizacao: string | null;
};

export type Filtros = { ufs: string[]; partidos: string[]; categorias: Categoria[] };

export type RegraAlerta = "valor_atipico_categoria_uf" | "concentracao_fornecedor" | "notas_repetidas" | "gasto_mensal_atipico";

export type DeputadoBasico = Omit<DeputadoResumo, "total_periodo" | "n_notas">;

export type Alerta = {
  id: number;
  regra: RegraAlerta;
  regra_nome: string;
  score: number;
  valor_referencia: number | null;
  explicacao: string;
  ano: number;
  mes: number | null; // nulo = alerta do ano inteiro
  criado_em: string;
  deputado: DeputadoBasico;
  categoria: Categoria | null;
  nota: { id: number; data_documento: string | null; valor_liquido: number; fornecedor_nome: string | null; url_documento: string | null } | null;
};

export type ContagemRegra = { regra: RegraAlerta; nome: string; quantidade: number };

export type Assinatura = { status: string; provedor: string; inicio: string | null; fim: string | null };
export type Usuario = { id: number; nome: string; email: string; plano: "free" | "pro"; criado_em: string; assinatura: Assinatura | null };
export type TokenResposta = { access_token: string; token_type: string; usuario: Usuario };
export type PlanoInfo = { id: "free" | "pro"; nome: string; preco_mensal: number; recursos: string[] };
export type Planos = { modo_pagamento: "simulado" | "stripe"; planos: PlanoInfo[] };
export type ResultadoAssinatura = { modo: string; plano: "free" | "pro"; checkout_url: string | null; mensagem: string };
export type TipoInscricao = "deputado" | "uf" | "categoria";
export type Inscricao = { id: number; tipo: TipoInscricao; valor: string; descricao: string; ativo: boolean; criado_em: string };
export type FiltrosExportacao = { de?: string; ate?: string; uf?: string; partido?: string; categoria?: string; deputado_id?: number };

// ------------------------------------------------------------- chamadas

export const api = {
  visaoGeral: (signal?: AbortSignal) => getJson<VisaoGeral>("/estatisticas/visao-geral", {}, signal),
  filtros: (signal?: AbortSignal) => getJson<Filtros>("/filtros", {}, signal),
  deputados: (
    params: { busca?: string; uf?: string; partido?: string; em_exercicio?: boolean; ordenar?: "nome" | "total"; pagina?: number; itens?: number },
    signal?: AbortSignal,
  ) => getJson<Pagina<DeputadoResumo>>("/deputados", params, signal),
  deputado: (id: number, signal?: AbortSignal) => getJson<DeputadoPerfil>(`/deputados/${id}`, {}, signal),
  despesas: (
    id: number,
    params: { categoria?: string; ordenar?: "data" | "valor"; pagina?: number; itens?: number },
    signal?: AbortSignal,
  ) => getJson<Pagina<Despesa>>(`/deputados/${id}/despesas`, params, signal),
  ranking: (
    params: { tipo: TipoRanking; categoria?: string; uf?: string; partido?: string; ordem?: "total" | "media"; limite?: number },
    signal?: AbortSignal,
  ) => getJson<Ranking>("/rankings", params, signal),
  alertas: (
    params: { regra?: RegraAlerta | ""; uf?: string; categoria?: string; pagina?: number; itens?: number },
    signal?: AbortSignal,
  ) => getJson<Pagina<Alerta>>("/alertas", params, signal),
  alertasPorRegra: (params: { uf?: string; categoria?: string }, signal?: AbortSignal) =>
    getJson<ContagemRegra[]>("/alertas/por-regra", params, signal),
  alertasDoDeputado: (id: number, params: { pagina?: number; itens?: number }, signal?: AbortSignal) =>
    getJson<Pagina<Alerta>>(`/deputados/${id}/alertas`, params, signal),

  // conta e plano Pro
  cadastro: (dados: { nome: string; email: string; senha: string }) => postJson<TokenResposta>("/auth/cadastro", dados),
  login: (dados: { email: string; senha: string }) => postJson<TokenResposta>("/auth/login", dados),
  me: (signal?: AbortSignal) => getJson<Usuario>("/auth/me", {}, signal),
  planos: (signal?: AbortSignal) => getJson<Planos>("/planos", {}, signal),
  assinar: () => postJson<ResultadoAssinatura>("/planos/assinar"),
  cancelar: () => postJson<ResultadoAssinatura>("/planos/cancelar"),
  exportarDespesas: (filtros: FiltrosExportacao) => baixarArquivo("/export/despesas.csv", filtros, "despesas.csv"),
  inscricoes: (signal?: AbortSignal) => getJson<Inscricao[]>("/me/inscricoes", {}, signal),
  criarInscricao: (tipo: TipoInscricao, valor: string) => postJson<Inscricao>("/me/inscricoes", { tipo, valor }),
  removerInscricao: (id: number) => deletar(`/me/inscricoes/${id}`),
};
