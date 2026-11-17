import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, type FiltrosExportacao, type TipoInscricao } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useApi } from "../hooks/useApi";

// Formata ISO -> "14/12/2026"
const dataCurta = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "—");

export default function MinhaConta() {
  const { usuario, recarregar } = useAuth();
  const [params] = useSearchParams();
  if (!usuario) return null; // a rota já exige login (RotaProtegida)
  const pro = usuario.plano === "pro";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-marca-900">Minha conta</h1>

      {params.get("assinatura") === "sucesso" && pro && (
        <p role="status" className="rounded-md bg-green-50 px-4 py-3 text-green-800">
          Pronto! Seu plano Pro está ativo.
        </p>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 font-semibold text-slate-900">Dados</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
          <dt className="text-slate-500">Nome</dt>
          <dd>{usuario.nome}</dd>
          <dt className="text-slate-500">E-mail</dt>
          <dd>{usuario.email}</dd>
          <dt className="text-slate-500">Plano</dt>
          <dd className="font-medium">{pro ? "Pro" : "Grátis"}</dd>
        </dl>
      </section>

      {pro ? <Assinatura aoMudar={recarregar} /> : <ConviteAssinar />}
      {pro && <Inscricoes />}
      {pro && <Exportacao />}
    </div>
  );
}

function ConviteAssinar() {
  return (
    <section className="rounded-lg border border-marca-100 bg-marca-50 p-5">
      <h2 className="font-semibold text-marca-900">Recursos do plano Pro</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">
        <li>Alertas por e-mail de deputados, estados ou categorias que você acompanha</li>
        <li>Exportação das despesas em CSV, com filtros</li>
        <li>Histórico completo: qualquer período disponível na base</li>
      </ul>
      <Link to="/planos" className="mt-4 inline-block rounded-md bg-marca-700 px-4 py-2 font-medium text-white hover:bg-marca-900">
        Conhecer o Pro
      </Link>
    </section>
  );
}

function Assinatura({ aoMudar }: { aoMudar: () => Promise<void> }) {
  const { usuario } = useAuth();
  const [confirmando, setConfirmando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const assinatura = usuario?.assinatura;

  const cancelar = async () => {
    setErro(null);
    try {
      await api.cancelar();
      await aoMudar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 font-semibold text-slate-900">Assinatura</h2>
      {assinatura && (
        <p className="text-sm text-slate-600">
          Ativa desde {dataCurta(assinatura.inicio)}
          {assinatura.fim ? `, válida até ${dataCurta(assinatura.fim)}` : ", renovação mensal"}
          {assinatura.provedor === "simulado" && " (modo simulado, sem cobrança)"}.
        </p>
      )}
      {/* Confirmação em duas etapas, sem janela do navegador */}
      {!confirmando ? (
        <button onClick={() => setConfirmando(true)} className="mt-3 text-sm text-red-700 hover:underline">
          Cancelar assinatura
        </button>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-md bg-red-50 p-3 text-sm">
          <span className="text-red-800">Cancelar agora? Você volta ao plano grátis na hora.</span>
          <button onClick={cancelar} className="rounded-md bg-red-700 px-3 py-1.5 font-medium text-white hover:bg-red-800">
            Sim, cancelar
          </button>
          <button onClick={() => setConfirmando(false)} className="text-slate-600 hover:underline">
            Manter
          </button>
        </div>
      )}
      {erro && <p className="mt-2 text-sm text-red-700">{erro}</p>}
    </section>
  );
}

const ROTULO_TIPO: Record<TipoInscricao, string> = { deputado: "Deputado", uf: "Estado", categoria: "Categoria" };

function Inscricoes() {
  const inscricoes = useApi((s) => api.inscricoes(s), []);
  const filtros = useApi((s) => api.filtros(s), []);
  const [tipo, setTipo] = useState<"uf" | "categoria">("uf");
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const adicionar = async (e: FormEvent) => {
    e.preventDefault();
    if (!valor) return;
    setErro(null);
    try {
      await api.criarInscricao(tipo, valor);
      setValor("");
      inscricoes.recarregar();
    } catch (falha) {
      setErro((falha as Error).message);
    }
  };

  const remover = async (id: number) => {
    try {
      await api.removerInscricao(id);
      inscricoes.recarregar();
    } catch (falha) {
      setErro((falha as Error).message);
    }
  };

  const campo = "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm";
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-slate-900">Alertas que você acompanha</h2>
      <p className="mt-1 text-sm text-slate-600">
        Quando surgir um novo gasto fora do padrão que bata com estes itens, você recebe um e-mail. Para acompanhar um
        deputado, use o botão “Acompanhar” no perfil dele.
      </p>

      {inscricoes.carregando && <p className="mt-3 text-sm text-slate-500">Carregando…</p>}
      {inscricoes.erro && <p className="mt-3 text-sm text-red-700">{inscricoes.erro}</p>}
      {inscricoes.dados && inscricoes.dados.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">Você ainda não acompanha nada.</p>
      )}
      {inscricoes.dados && inscricoes.dados.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100">
          {inscricoes.dados.map((i) => (
            <li key={i.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span>
                <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{ROTULO_TIPO[i.tipo]}</span>
                {i.tipo === "deputado" ? (
                  <Link to={`/deputados/${i.valor}`} className="hover:underline">
                    {i.descricao}
                  </Link>
                ) : (
                  i.descricao
                )}
              </span>
              <button onClick={() => remover(i.id)} className="text-slate-500 hover:text-red-700 hover:underline">
                Remover
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={adicionar} className="mt-4 flex flex-wrap items-center gap-2">
        <select
          aria-label="Tipo"
          className={campo}
          value={tipo}
          onChange={(e) => {
            setTipo(e.target.value as "uf" | "categoria");
            setValor("");
          }}
        >
          <option value="uf">Estado</option>
          <option value="categoria">Categoria</option>
        </select>
        <select aria-label={tipo === "uf" ? "Estado" : "Categoria"} className={campo} value={valor} onChange={(e) => setValor(e.target.value)}>
          <option value="">Escolha…</option>
          {tipo === "uf"
            ? filtros.dados?.ufs.map((u) => <option key={u}>{u}</option>)
            : filtros.dados?.categorias.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.nome}
                </option>
              ))}
        </select>
        <button type="submit" disabled={!valor} className="rounded-md bg-marca-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-marca-900 disabled:opacity-50">
          Acompanhar
        </button>
      </form>
      {erro && <p className="mt-2 text-sm text-red-700">{erro}</p>}
    </section>
  );
}

function Exportacao() {
  const filtros = useApi((s) => api.filtros(s), []);
  const [form, setForm] = useState<FiltrosExportacao>({});
  const [estado, setEstado] = useState<"parado" | "baixando" | "erro">("parado");
  const [erro, setErro] = useState("");

  const mudar = (campo: keyof FiltrosExportacao, valor: string) => setForm((f) => ({ ...f, [campo]: valor || undefined }));

  const exportar = async (e: FormEvent) => {
    e.preventDefault();
    setEstado("baixando");
    try {
      await api.exportarDespesas(form);
      setEstado("parado");
    } catch (falha) {
      setErro((falha as Error).message);
      setEstado("erro");
    }
  };

  const campo = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm";
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-slate-900">Exportar despesas (CSV)</h2>
      <p className="mt-1 text-sm text-slate-600">
        Arquivo pronto para o Excel ou Google Planilhas: separador “;”, vírgula decimal e link de cada nota. Sem filtros, o
        período padrão é o dos últimos 12 meses.
      </p>
      <form onSubmit={exportar} className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="text-sm text-slate-700">
          De (mês)
          <input type="month" className={campo} value={form.de ?? ""} onChange={(e) => mudar("de", e.target.value)} />
        </label>
        <label className="text-sm text-slate-700">
          Até (mês)
          <input type="month" className={campo} value={form.ate ?? ""} onChange={(e) => mudar("ate", e.target.value)} />
        </label>
        <label className="text-sm text-slate-700">
          Estado
          <select className={campo} value={form.uf ?? ""} onChange={(e) => mudar("uf", e.target.value)}>
            <option value="">Todos</option>
            {filtros.dados?.ufs.map((u) => (
              <option key={u}>{u}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-700">
          Categoria
          <select className={campo} value={form.categoria ?? ""} onChange={(e) => mudar("categoria", e.target.value)}>
            <option value="">Todas</option>
            {filtros.dados?.categorias.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nome}
              </option>
            ))}
          </select>
        </label>
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={estado === "baixando"}
            className="rounded-md bg-marca-700 px-4 py-2 font-medium text-white hover:bg-marca-900 disabled:opacity-60"
          >
            {estado === "baixando" ? "Gerando o arquivo…" : "Baixar CSV"}
          </button>
          {estado === "erro" && <p className="mt-2 text-sm text-red-700">{erro}</p>}
        </div>
      </form>
    </section>
  );
}
