import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ValorPorMes } from "../../api/client";
import { mesCurto, moeda, moedaCompacta, numero } from "../../lib/formato";
import CartaoGrafico, { CaixaTooltip, TabelaSimples } from "./CartaoGrafico";

type Linha = ValorPorMes & { rotulo: string };

// Colunas por mês: cada mês é um valor separado (total do mês), por isso
// colunas e não linha. Uma linha sugeriria continuidade entre os meses.
export default function GraficoMensal({ dados, titulo = "Gasto por mês" }: { dados: ValorPorMes[]; titulo?: string }) {
  const linhas: Linha[] = dados.map((d) => ({ ...d, rotulo: mesCurto(d.ano, d.mes) }));

  return (
    <CartaoGrafico
      titulo={titulo}
      subtitulo="Os meses mais recentes ainda recebem notas: o deputado tem até 90 dias para apresentá-las."
      grafico={
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={linhas} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap="25%">
            {/* Grade só horizontal, fina e clara: guia o olho sem competir com os dados */}
            <CartesianGrid vertical={false} stroke="var(--grafico-grade)" />
            <XAxis
              dataKey="rotulo"
              tickLine={false}
              axisLine={{ stroke: "var(--grafico-grade)" }}
              tick={{ fill: "var(--grafico-eixo)", fontSize: 12 }}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v) => moedaCompacta(Number(v))}
              tickLine={false}
              axisLine={false}
              width={72}
              tick={{ fill: "var(--grafico-eixo)", fontSize: 12 }}
            />
            <Tooltip
              cursor={{ fill: "var(--grafico-grade)", opacity: 0.6 }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const l = payload[0].payload as Linha;
                return (
                  <CaixaTooltip
                    titulo={l.rotulo}
                    linhas={[
                      ["Total", moeda(l.total)],
                      ["Notas", numero(l.n_notas)],
                    ]}
                  />
                );
              }}
            />
            <Bar dataKey="total" fill="var(--grafico-serie-1)" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      }
      tabela={
        <TabelaSimples
          cabecalho={["Mês", "Total", "Notas"]}
          linhas={linhas.map((l) => [l.rotulo, moeda(l.total), numero(l.n_notas)])}
        />
      }
    />
  );
}
