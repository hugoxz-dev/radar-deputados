import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ValorPorCategoria } from "../../api/client";
import { useTelaEstreita } from "../../hooks/useTelaEstreita";
import { moeda, moedaCompacta, numero } from "../../lib/formato";
import CartaoGrafico, { CaixaTooltip, TabelaSimples } from "./CartaoGrafico";

const MAX_BARRAS = 8;

type Linha = { nome: string; total: number; percentual: number; n_notas: number };

// Barras horizontais: a melhor forma para comparar valores entre categorias
// com nomes longos (o nome cabe na horizontal, sem girar texto).
// Mostra as 8 maiores; o resto vira "Outras", para o gráfico não virar uma lista enorme.
function agrupar(dados: ValorPorCategoria[]): Linha[] {
  const linhas = dados.map((d) => ({ nome: d.categoria.nome, total: d.total, percentual: d.percentual, n_notas: d.n_notas }));
  if (linhas.length <= MAX_BARRAS) return linhas;
  const resto = linhas.slice(MAX_BARRAS - 1);
  return [
    ...linhas.slice(0, MAX_BARRAS - 1),
    {
      nome: `Outras (${resto.length})`,
      total: resto.reduce((s, l) => s + l.total, 0),
      percentual: Math.round(resto.reduce((s, l) => s + l.percentual, 0) * 100) / 100,
      n_notas: resto.reduce((s, l) => s + l.n_notas, 0),
    },
  ];
}

export default function GraficoCategorias({ dados, titulo = "Gasto por categoria" }: { dados: ValorPorCategoria[]; titulo?: string }) {
  const linhas = agrupar(dados);
  const altura = linhas.length * 36 + 16;
  const estreita = useTelaEstreita();
  // No celular, a coluna de nomes encolhe e nomes longos ganham reticências
  const larguraNomes = estreita ? 112 : 190;
  // (o nome completo continua no tooltip e na tabela)
  const encurtar = (nome: string) => (estreita && nome.length > 13 ? `${nome.slice(0, 11).trimEnd()}…` : nome);

  return (
    <CartaoGrafico
      titulo={titulo}
      subtitulo="Valor líquido reembolsado no período"
      grafico={
        <ResponsiveContainer width="100%" height={altura}>
          <BarChart data={linhas} layout="vertical" margin={{ top: 0, right: 72, bottom: 0, left: 0 }} barCategoryGap={6}>
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="nome"
              width={larguraNomes}
              tickLine={false}
              axisLine={false}
              tickFormatter={encurtar}
              tick={{ fill: "var(--grafico-eixo)", fontSize: estreita ? 12 : 13 }}
            />
            <Tooltip
              cursor={{ fill: "var(--grafico-grade)", opacity: 0.6 }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const l = payload[0].payload as Linha;
                return (
                  <CaixaTooltip
                    titulo={l.nome}
                    linhas={[
                      ["Total", moeda(l.total)],
                      ["Do total", `${l.percentual.toLocaleString("pt-BR")}%`],
                      ["Notas", numero(l.n_notas)],
                    ]}
                  />
                );
              }}
            />
            {/* radius: ponta arredondada só no fim da barra; maxBarSize: barra fina (≤ 24px) */}
            {/* Sem animação de entrada: o gráfico aparece pronto (e o rótulo de valor junto) */}
            <Bar dataKey="total" fill="var(--grafico-serie-1)" radius={[0, 4, 4, 0]} maxBarSize={24} isAnimationActive={false}>
              <LabelList
                dataKey="total"
                position="right"
                formatter={(v) => moedaCompacta(Number(v))}
                style={{ fill: "var(--grafico-texto)", fontSize: 12 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      }
      tabela={
        <TabelaSimples
          cabecalho={["Categoria", "Total", "%", "Notas"]}
          linhas={dados.map((d) => [d.categoria.nome, moeda(d.total), `${d.percentual.toLocaleString("pt-BR")}%`, numero(d.n_notas)])}
        />
      }
    />
  );
}
