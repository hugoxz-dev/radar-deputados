import { Link } from "react-router-dom";

import { api } from "../api/client";
import BuscaDeputado from "../components/BuscaDeputado";
import { Carregando, Erro } from "../components/Estado";
import FotoDeputado from "../components/FotoDeputado";
import GraficoCategorias from "../components/graficos/GraficoCategorias";
import GraficoMensal from "../components/graficos/GraficoMensal";
import StatTile from "../components/StatTile";
import { useApi } from "../hooks/useApi";
import { dataHora, mesPorExtenso, moeda, moedaCompacta, numero } from "../lib/formato";

// Página inicial: busca + visão geral do período (cards, gráficos e quem mais gastou).
export default function Home() {
  const visao = useApi((s) => api.visaoGeral(s), []);
  const top = useApi((s) => api.ranking({ tipo: "deputado", limite: 5 }, s), []);

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-3xl font-bold tracking-tight text-marca-900 sm:text-4xl">
          Como os deputados federais usam a cota parlamentar
        </h1>
        <p className="max-w-3xl text-slate-600">
          A Cota para o Exercício da Atividade Parlamentar (CEAP) reembolsa gastos como combustível, passagens,
          alimentação e divulgação do mandato. Aqui você vê, com dados oficiais da Câmara, quanto cada deputado
          gastou e em quê.
        </p>
        <BuscaDeputado />
      </section>

      {visao.carregando && <Carregando texto="Carregando a visão geral…" />}
      {visao.erro && <Erro mensagem={visao.erro} aoTentarDeNovo={visao.recarregar} />}
      {visao.dados && (
        <>
          <p className="text-sm text-slate-500">
            Período: <strong className="font-medium text-slate-700">{mesPorExtenso(visao.dados.periodo.de)}</strong> a{" "}
            <strong className="font-medium text-slate-700">{mesPorExtenso(visao.dados.periodo.ate)}</strong>
            {visao.dados.ultima_atualizacao && <> · dados atualizados em {dataHora(visao.dados.ultima_atualizacao)}</>}
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              rotulo="Total gasto"
              valor={moedaCompacta(visao.dados.total)}
              detalhe={`${numero(visao.dados.n_notas)} notas fiscais e recibos`}
            />
            <StatTile
              rotulo="Média por deputado"
              valor={moedaCompacta(visao.dados.media_por_deputado)}
              detalhe={`${numero(visao.dados.n_deputados_com_gasto)} deputados com gastos`}
            />
            <StatTile
              rotulo="Categoria mais cara"
              valor={<span className="block text-lg leading-snug">{visao.dados.categoria_mais_cara?.categoria.nome ?? "—"}</span>}
              detalhe={
                visao.dados.categoria_mais_cara &&
                `${moedaCompacta(visao.dados.categoria_mais_cara.total)} · ${visao.dados.categoria_mais_cara.percentual.toLocaleString("pt-BR")}% do total`
              }
            />
            <Link to="/alertas" className="rounded-lg transition hover:ring-2 hover:ring-marca-100">
              <StatTile
                rotulo="Gastos fora do padrão"
                valor={numero(visao.dados.n_alertas)}
                detalhe={<>destaques estatísticos, não indicam irregularidade · <span className="text-marca-700">ver →</span></>}
              />
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <GraficoCategorias dados={visao.dados.por_categoria} />
            <GraficoMensal dados={visao.dados.por_mes} />
          </div>
        </>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="mb-3 flex items-baseline justify-between gap-4">
          <h2 className="font-semibold text-slate-900">Quem mais gastou no período</h2>
          <Link to="/rankings?tipo=deputado" className="text-sm text-marca-700 hover:underline">
            Ver ranking completo →
          </Link>
        </div>
        {top.carregando && <Carregando altura="h-24" />}
        {top.erro && <Erro mensagem={top.erro} aoTentarDeNovo={top.recarregar} />}
        {top.dados && (
          <ol className="divide-y divide-slate-100">
            {top.dados.itens.map((item) => (
              <li key={item.chave}>
                <Link to={`/deputados/${item.chave}`} className="flex items-center gap-3 py-2.5 hover:bg-slate-50">
                  <span className="w-5 text-right text-sm tabular-nums text-slate-400">{item.posicao}</span>
                  <FotoDeputado url={item.url_foto} nome={item.nome} tamanho="h-9 w-9" />
                  <span className="flex-1">
                    <span className="font-medium text-slate-800">{item.nome}</span>{" "}
                    <span className="text-sm text-slate-500">
                      {item.partido}-{item.uf}
                    </span>
                  </span>
                  <span className="font-medium tabular-nums text-slate-900">{moeda(item.total)}</span>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
