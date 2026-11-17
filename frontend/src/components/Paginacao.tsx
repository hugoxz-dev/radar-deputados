import { numero } from "../lib/formato";

export default function Paginacao({
  pagina,
  total,
  porPagina,
  aoMudar,
}: {
  pagina: number;
  total: number;
  porPagina: number;
  aoMudar: (pagina: number) => void;
}) {
  const ultima = Math.max(1, Math.ceil(total / porPagina));
  if (ultima === 1) return null;
  const botao = "rounded-md px-3 py-1.5 text-sm ring-1 ring-slate-300 enabled:hover:bg-slate-100 disabled:opacity-40";
  return (
    <nav className="flex items-center justify-between gap-4 pt-4 text-sm text-slate-600" aria-label="Paginação">
      <span>
        Página {numero(pagina)} de {numero(ultima)} · {numero(total)} itens
      </span>
      <div className="flex gap-2">
        <button className={botao} disabled={pagina <= 1} onClick={() => aoMudar(pagina - 1)}>
          Anterior
        </button>
        <button className={botao} disabled={pagina >= ultima} onClick={() => aoMudar(pagina + 1)}>
          Próxima
        </button>
      </div>
    </nav>
  );
}
