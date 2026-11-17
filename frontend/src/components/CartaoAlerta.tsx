import { Link } from "react-router-dom";

import type { Alerta } from "../api/client";
import { data, mesCurto, moeda } from "../lib/formato";
import FotoDeputado from "./FotoDeputado";

// Um alerta no feed. Visual sóbrio de propósito (sem vermelho, sem ícone de perigo):
// é um destaque estatístico, não uma acusação.
export default function CartaoAlerta({ alerta, mostrarDeputado = true }: { alerta: Alerta; mostrarDeputado?: boolean }) {
  const quando = alerta.mes ? mesCurto(alerta.ano, alerta.mes) : `ano de ${alerta.ano}`;
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-marca-50 px-2.5 py-0.5 font-medium text-marca-700 ring-1 ring-marca-100">
          {alerta.regra_nome}
        </span>
        <span className="text-slate-500">{quando}</span>
        {alerta.categoria && <span className="text-slate-500">· {alerta.categoria.nome}</span>}
      </div>

      {mostrarDeputado && (
        <Link to={`/deputados/${alerta.deputado.id}`} className="mt-3 flex items-center gap-2 hover:underline">
          <FotoDeputado url={alerta.deputado.url_foto} nome={alerta.deputado.nome} tamanho="h-8 w-8" />
          <span className="font-medium text-slate-900">{alerta.deputado.nome}</span>
          <span className="text-sm text-slate-500">
            {alerta.deputado.partido}-{alerta.deputado.uf}
          </span>
        </Link>
      )}

      <p className="mt-2 leading-relaxed text-slate-800">{alerta.explicacao}</p>

      {alerta.nota && (
        <p className="mt-2 text-sm text-slate-500">
          Nota de {data(alerta.nota.data_documento)} · {moeda(alerta.nota.valor_liquido)}
          {alerta.nota.fornecedor_nome && ` · ${alerta.nota.fornecedor_nome}`}
          {alerta.nota.url_documento && (
            <>
              {" · "}
              <a href={alerta.nota.url_documento} target="_blank" rel="noreferrer" className="text-marca-700 hover:underline">
                ver nota original ↗
              </a>
            </>
          )}
        </p>
      )}
    </article>
  );
}
