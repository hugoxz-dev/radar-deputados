import { useState, type ReactNode } from "react";

// Moldura comum dos gráficos: título, subtítulo e o botão "ver como tabela".
// A tabela é a alternativa acessível ao gráfico: leitores de tela e quem
// prefere números exatos leem os mesmos dados sem depender de cor ou hover.
export default function CartaoGrafico({
  titulo,
  subtitulo,
  grafico,
  tabela,
}: {
  titulo: string;
  subtitulo?: ReactNode;
  grafico: ReactNode;
  tabela: ReactNode;
}) {
  const [verTabela, setVerTabela] = useState(false);
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold text-slate-900">{titulo}</h2>
          {subtitulo && <p className="mt-0.5 text-sm text-slate-500">{subtitulo}</p>}
        </div>
        <button
          onClick={() => setVerTabela((v) => !v)}
          className="rounded-md px-2.5 py-1 text-sm text-marca-700 ring-1 ring-slate-200 hover:bg-slate-50"
          aria-pressed={verTabela}
        >
          {verTabela ? "Ver gráfico" : "Ver como tabela"}
        </button>
      </div>
      {verTabela ? <div className="max-h-80 overflow-auto">{tabela}</div> : grafico}
    </section>
  );
}

export function TabelaSimples({ cabecalho, linhas }: { cabecalho: string[]; linhas: ReactNode[][] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-200 text-left text-slate-500">
          {cabecalho.map((c, i) => (
            <th key={c} className={`py-2 font-medium ${i > 0 ? "text-right" : ""}`}>
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((linha, i) => (
          <tr key={i} className="border-b border-slate-100 last:border-0">
            {linha.map((celula, j) => (
              <td key={j} className={`py-1.5 ${j > 0 ? "text-right tabular-nums" : ""}`}>
                {celula}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Caixa do tooltip (aparece no hover). Texto sempre em cor de texto, nunca na cor da série.
export function CaixaTooltip({ titulo, linhas }: { titulo: string; linhas: [string, string][] }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-md">
      <p className="mb-1 font-medium text-slate-900">{titulo}</p>
      {linhas.map(([rotulo, valor]) => (
        <p key={rotulo} className="flex justify-between gap-4 text-slate-600">
          <span>{rotulo}</span>
          <span className="font-medium tabular-nums text-slate-900">{valor}</span>
        </p>
      ))}
    </div>
  );
}
