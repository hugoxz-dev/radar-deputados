import type { ReactNode } from "react";

// Card de número em destaque: rótulo, valor e uma linha de contexto opcional.
export default function StatTile({ rotulo, valor, detalhe }: { rotulo: string; valor: ReactNode; detalhe?: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{rotulo}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{valor}</p>
      {detalhe && <p className="mt-1 text-sm text-slate-600">{detalhe}</p>}
    </div>
  );
}
