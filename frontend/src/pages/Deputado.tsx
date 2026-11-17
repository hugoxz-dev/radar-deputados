import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type DeputadoPerfil } from "../api/client";
import BotaoAcompanhar from "../components/BotaoAcompanhar";
import CartaoAlerta from "../components/CartaoAlerta";
import { Carregando, Erro, Vazio } from "../components/Estado";
import FotoDeputado from "../components/FotoDeputado";
import GraficoCategorias from "../components/graficos/GraficoCategorias";
import GraficoMensal from "../components/graficos/GraficoMensal";
import Paginacao from "../components/Paginacao";
import StatTile from "../components/StatTile";
import { useApi } from "../hooks/useApi";
import { data, dataHora, documento, mesCurto, mesPorExtenso, moeda, moedaCompacta, numero } from "../lib/formato";

export default function Deputado() {
  const id = Number(useParams().id);
  const perfil = useApi((s) => api.deputado(id, s), [id]);

  if (perfil.carregando) return <Carregando texto="Carregando o perfil…" altura="h-64" />;
  if (perfil.erro || !perfil.dados) {
    // 404 tem mensagem própria; outros erros oferecem "tentar de novo"
    return perfil.statusErro === 404 ? (
      <Vazio titulo="Deputado não encontrado." detalhe="Confira o endereço ou use a busca na página inicial." />
    ) : (
      <Erro mensagem={perfil.erro ?? "Erro desconhecido"} aoTentarDeNovo={perfil.recarregar} />
    );
  }
  return <Perfil p={perfil.dados} />;
}

function Perfil({ p }: { p: DeputadoPerfil }) {
  const comp = p.comparacao_uf;
  return (
    <div className="space-y-6">
      <nav className="text-sm text-slate-500">
        <Link to="/" className="hover:underline">
          Início
        </Link>{" "}
        / {p.nome}
      </nav>

      {/* Cabeçalho */}
      <header className="flex flex-wrap items-center gap-5">
        <FotoDeputado url={p.url_foto} nome={p.nome} tamanho="h-24 w-24" />
        <div className="min-w-0 flex-1">
          <h1 className="text-3xl font-bold tracking-tight text-marca-900">{p.nome}</h1>
          <p className="mt-1 text-slate-600">
            {p.partido} · {p.uf} ·{" "}
            {p.em_exercicio ? (
              <span className="font-medium text-green-700">em exercício</span>
            ) : (
              <span className="text-slate-500">fora do exercício</span>
            )}
          </p>
          {p.nome_civil && <p className="mt-0.5 text-sm text-slate-500">Nome civil: {p.nome_civil}</p>}
          {p.email && <p className="text-sm text-slate-500">{p.email}</p>}
        </div>
        <BotaoAcompanhar deputadoId={p.id} />
      </header>

      <p className="text-sm text-slate-500">
        Período: {mesPorExtenso(p.periodo.de)} a {mesPorExtenso(p.periodo.ate)}
      </p>

      <ResumoEmDestaque resumo={p.resumo_ia} />

      {/* Números principais */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile rotulo="Total gasto" valor={moedaCompacta(p.total)} detalhe={`${numero(p.n_notas)} notas`} />
        <StatTile rotulo="Média mensal" valor={moedaCompacta(p.media_mensal)} detalhe="total ÷ meses do período" />
        <StatTile
          rotulo={`Comparado aos deputados de ${p.uf}`}
          valor={comp?.razao != null ? `${comp.razao.toLocaleString("pt-BR")}× a mediana` : "—"}
          detalhe={comp && `mediana de ${comp.n_deputados_uf} deputados: ${moedaCompacta(comp.mediana_uf)}`}
        />
        <StatTile
          rotulo="Gastos fora do padrão"
          valor={numero(p.n_alertas)}
          detalhe="destaques estatísticos, não indicam irregularidade"
        />
      </div>

      {p.n_notas === 0 ? (
        <Vazio titulo="Nenhuma despesa no período." detalhe="Este deputado não apresentou notas nestes meses." />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <GraficoMensal dados={p.por_mes} />
            <GraficoCategorias dados={p.por_categoria} />
          </div>
          <AlertasDoDeputado p={p} />
          <MaioresFornecedores p={p} />
          <TabelaDespesas p={p} />
        </>
      )}
    </div>
  );
}

// Resumo em linguagem simples. O selo diz a verdade sobre quem escreveu:
// "gerado por IA" quando foi um LLM; "automático" quando foi o template (sem IA).
function ResumoEmDestaque({ resumo }: { resumo: DeputadoPerfil["resumo_ia"] }) {
  const porIA = resumo !== null && resumo.modelo_usado !== "template";
  return (
    <section className="rounded-lg border border-marca-100 bg-marca-50 p-5">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 className="font-semibold text-marca-900">Resumo em linguagem simples</h2>
        {resumo && (
          <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-marca-700 ring-1 ring-marca-100">
            {porIA ? "resumo gerado por IA" : "resumo automático"}
          </span>
        )}
      </div>
      {resumo ? (
        <>
          <p className="leading-relaxed text-slate-800">{resumo.texto}</p>
          <p className="mt-2 text-xs text-slate-500">
            {porIA
              ? `Escrito por um modelo de IA (${resumo.modelo_usado}) a partir dos números desta página; os números são conferidos automaticamente antes de publicar.`
              : "Montado automaticamente a partir dos números desta página (sem IA)."}{" "}
            Gerado em {dataHora(resumo.gerado_em)}.
          </p>
        </>
      ) : (
        <p className="text-slate-600">O resumo deste deputado ainda não foi gerado.</p>
      )}
    </section>
  );
}

const ALERTAS_POR_PAGINA = 5;

function AlertasDoDeputado({ p }: { p: DeputadoPerfil }) {
  const [pagina, setPagina] = useState(1);
  const alertas = useApi((s) => api.alertasDoDeputado(p.id, { pagina, itens: ALERTAS_POR_PAGINA }, s), [p.id, pagina]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold text-slate-900">Gastos fora do padrão</h2>
        <Link to="/metodologia" className="text-sm text-marca-700 hover:underline">
          Como são calculados?
        </Link>
      </div>
      <p className="mb-3 text-sm text-slate-500">
        Destaques estatísticos: um gasto fora do padrão <strong>não significa irregularidade</strong>.
      </p>
      {alertas.carregando && <Carregando altura="h-24" />}
      {alertas.erro && <Erro mensagem={alertas.erro} aoTentarDeNovo={alertas.recarregar} />}
      {alertas.dados && alertas.dados.itens.length === 0 && (
        <p className="text-slate-600">Nenhum gasto fora do padrão encontrado no período.</p>
      )}
      {alertas.dados && alertas.dados.itens.length > 0 && (
        <div className="space-y-3">
          {alertas.dados.itens.map((a) => (
            <CartaoAlerta key={a.id} alerta={a} mostrarDeputado={false} />
          ))}
          <Paginacao pagina={pagina} total={alertas.dados.total} porPagina={ALERTAS_POR_PAGINA} aoMudar={setPagina} />
        </div>
      )}
    </section>
  );
}

function MaioresFornecedores({ p }: { p: DeputadoPerfil }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <h2 className="mb-3 font-semibold text-slate-900">Maiores fornecedores</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="py-2 font-medium">Fornecedor</th>
              <th className="py-2 font-medium">CNPJ/CPF</th>
              <th className="py-2 pl-4 text-right font-medium">Notas</th>
              <th className="py-2 pl-4 text-right font-medium">Total</th>
              <th className="py-2 pl-4 text-right font-medium whitespace-nowrap">% do deputado</th>
            </tr>
          </thead>
          <tbody>
            {p.top_fornecedores.map((f) => (
              <tr key={f.cnpj_cpf ?? f.nome} className="border-b border-slate-100 last:border-0">
                <td className="py-2 pr-4">{f.nome}</td>
                <td className="py-2 pr-4 whitespace-nowrap text-slate-500">{documento(f.cnpj_cpf)}</td>
                <td className="py-2 pl-4 text-right tabular-nums">{numero(f.n_notas)}</td>
                <td className="py-2 pl-4 text-right whitespace-nowrap tabular-nums">{moeda(f.total)}</td>
                <td className="py-2 pl-4 text-right tabular-nums">
                  {p.total ? `${((f.total / p.total) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const POR_PAGINA = 20;

function TabelaDespesas({ p }: { p: DeputadoPerfil }) {
  const [categoria, setCategoria] = useState("");
  const [ordenar, setOrdenar] = useState<"data" | "valor">("data");
  const [pagina, setPagina] = useState(1);
  const despesas = useApi(
    (s) => api.despesas(p.id, { categoria, ordenar, pagina, itens: POR_PAGINA }, s),
    [p.id, categoria, ordenar, pagina],
  );

  const select = "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm";
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-900">Notas fiscais e recibos</h2>
        <div className="flex flex-wrap gap-2">
          <label className="sr-only" htmlFor="filtro-categoria">
            Categoria
          </label>
          <select
            id="filtro-categoria"
            className={select}
            value={categoria}
            onChange={(e) => {
              setCategoria(e.target.value);
              setPagina(1);
            }}
          >
            <option value="">Todas as categorias</option>
            {p.por_categoria.map((c) => (
              <option key={c.categoria.slug} value={c.categoria.slug}>
                {c.categoria.nome}
              </option>
            ))}
          </select>
          <label className="sr-only" htmlFor="ordenar-despesas">
            Ordenar
          </label>
          <select
            id="ordenar-despesas"
            className={select}
            value={ordenar}
            onChange={(e) => {
              setOrdenar(e.target.value as "data" | "valor");
              setPagina(1);
            }}
          >
            <option value="data">Mais recentes</option>
            <option value="valor">Maior valor</option>
          </select>
        </div>
      </div>

      {despesas.carregando && <Carregando altura="h-32" />}
      {despesas.erro && <Erro mensagem={despesas.erro} aoTentarDeNovo={despesas.recarregar} />}
      {despesas.dados && despesas.dados.itens.length === 0 && <Vazio titulo="Nenhuma nota com esses filtros." />}
      {despesas.dados && despesas.dados.itens.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="py-2 font-medium">Data</th>
                  <th className="py-2 font-medium">Categoria</th>
                  <th className="py-2 font-medium">Fornecedor</th>
                  <th className="py-2 text-right font-medium">Valor</th>
                  <th className="py-2 text-right font-medium">Nota</th>
                </tr>
              </thead>
              <tbody>
                {despesas.dados.itens.map((d) => (
                  <tr key={d.id} className="border-b border-slate-100 align-top last:border-0">
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {data(d.data_documento)}
                      <span className="block text-xs text-slate-400">ref. {mesCurto(d.ano, d.mes)}</span>
                    </td>
                    <td className="py-2 pr-3">{d.categoria.nome}</td>
                    <td className="py-2 pr-3">
                      {d.fornecedor_nome ?? "—"}
                      <span className="block text-xs text-slate-400">{documento(d.fornecedor_cnpj_cpf)}</span>
                    </td>
                    <td className="py-2 text-right whitespace-nowrap tabular-nums">
                      {moeda(d.valor_liquido)}
                      {d.valor_glosa > 0 && (
                        <span className="block text-xs text-slate-400" title="Parte da nota que a Câmara não reembolsou">
                          glosa {moeda(d.valor_glosa)}
                        </span>
                      )}
                      {d.valor_liquido < 0 && <span className="block text-xs text-slate-400">crédito/estorno</span>}
                    </td>
                    <td className="py-2 text-right">
                      {d.url_documento ? (
                        <a href={d.url_documento} target="_blank" rel="noreferrer" className="text-marca-700 hover:underline">
                          ver nota ↗
                        </a>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao pagina={pagina} total={despesas.dados.total} porPagina={POR_PAGINA} aoMudar={setPagina} />
        </>
      )}
    </section>
  );
}
