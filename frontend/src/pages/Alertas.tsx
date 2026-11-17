import { Link, useSearchParams } from "react-router-dom";

import { api, type RegraAlerta } from "../api/client";
import CartaoAlerta from "../components/CartaoAlerta";
import { Carregando, Erro, Vazio } from "../components/Estado";
import Paginacao from "../components/Paginacao";
import { useApi } from "../hooks/useApi";
import { numero } from "../lib/formato";

const POR_PAGINA = 20;

// Feed público de gastos fora do padrão, com filtros na URL (compartilháveis).
export default function Alertas() {
  const [params, setParams] = useSearchParams();
  const regra = (params.get("regra") ?? "") as RegraAlerta | "";
  const uf = params.get("uf") ?? "";
  const categoria = params.get("categoria") ?? "";
  const pagina = Number(params.get("pagina") ?? 1);

  const filtros = useApi((s) => api.filtros(s), []);
  const contagem = useApi((s) => api.alertasPorRegra({ uf, categoria }, s), [uf, categoria]);
  const alertas = useApi(
    (s) => api.alertas({ regra, uf, categoria, pagina, itens: POR_PAGINA }, s),
    [regra, uf, categoria, pagina],
  );

  const mudar = (novos: Record<string, string>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(novos)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    if (!("pagina" in novos)) p.delete("pagina"); // filtro novo volta para a página 1
    setParams(p);
  };

  const total = contagem.dados?.reduce((s, c) => s + c.quantidade, 0) ?? 0;
  const chip = (ativo: boolean) =>
    `rounded-full px-3 py-1.5 text-sm ring-1 ${ativo ? "bg-marca-700 text-white ring-marca-700" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50"}`;
  const select = "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-900">Gastos fora do padrão</h1>
        <p className="mt-1 max-w-3xl text-slate-600">
          Notas e meses com valores muito diferentes do comum, encontrados por regras estatísticas.
        </p>
        <p className="mt-3 max-w-3xl rounded-md border border-marca-100 bg-marca-50 px-4 py-3 text-sm text-slate-700">
          <strong>Um gasto fora do padrão não significa irregularidade.</strong> Muitos têm explicação simples, como
          uma viagem longa ou um evento. Use os destaques como ponto de partida para consultar a nota original.{" "}
          <Link to="/metodologia" className="font-medium text-marca-700 hover:underline">
            Como os destaques são calculados →
          </Link>
        </p>
      </div>

      {/* Filtros por regra (com contagem) */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por regra">
        <button className={chip(!regra)} onClick={() => mudar({ regra: "" })}>
          Todas {contagem.dados && <span className="opacity-75">({numero(total)})</span>}
        </button>
        {contagem.dados?.map((c) => (
          <button key={c.regra} className={chip(regra === c.regra)} onClick={() => mudar({ regra: c.regra })}>
            {c.nome} <span className="opacity-75">({numero(c.quantidade)})</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Estado" className={select} value={uf} onChange={(e) => mudar({ uf: e.target.value })}>
          <option value="">Todos os estados</option>
          {filtros.dados?.ufs.map((u) => (
            <option key={u}>{u}</option>
          ))}
        </select>
        <select aria-label="Categoria" className={select} value={categoria} onChange={(e) => mudar({ categoria: e.target.value })}>
          <option value="">Todas as categorias</option>
          {filtros.dados?.categorias.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.nome}
            </option>
          ))}
        </select>
        {(regra || uf || categoria) && (
          <button className="text-sm text-marca-700 hover:underline" onClick={() => mudar({ regra: "", uf: "", categoria: "" })}>
            Limpar filtros
          </button>
        )}
      </div>

      {alertas.carregando && <Carregando texto="Carregando os destaques…" />}
      {alertas.erro && <Erro mensagem={alertas.erro} aoTentarDeNovo={alertas.recarregar} />}
      {alertas.dados && alertas.dados.itens.length === 0 && (
        <Vazio titulo="Nenhum gasto fora do padrão com esses filtros." detalhe="Tente outro estado, categoria ou regra." />
      )}
      {alertas.dados && alertas.dados.itens.length > 0 && (
        <div className="space-y-3">
          {alertas.dados.itens.map((a) => (
            <CartaoAlerta key={a.id} alerta={a} />
          ))}
          <Paginacao
            pagina={pagina}
            total={alertas.dados.total}
            porPagina={POR_PAGINA}
            aoMudar={(p) => {
              mudar({ pagina: String(p) });
              window.scrollTo(0, 0);
            }}
          />
        </div>
      )}
    </div>
  );
}
