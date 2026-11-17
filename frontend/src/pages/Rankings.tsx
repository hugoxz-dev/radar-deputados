import { Link, useSearchParams } from "react-router-dom";

import { api, type ItemRanking, type TipoRanking } from "../api/client";
import { Carregando, Erro, Vazio } from "../components/Estado";
import FotoDeputado from "../components/FotoDeputado";
import { useApi } from "../hooks/useApi";
import { mesPorExtenso, moeda, numero } from "../lib/formato";

const ABAS: { tipo: TipoRanking; rotulo: string }[] = [
  { tipo: "categoria", rotulo: "Por categoria" },
  { tipo: "uf", rotulo: "Por estado" },
  { tipo: "partido", rotulo: "Por partido" },
  { tipo: "deputado", rotulo: "Por deputado" },
];

// Os filtros ficam na URL (?tipo=uf&ordem=media...): dá para compartilhar o
// link de um ranking específico e o botão "voltar" do navegador funciona.
export default function Rankings() {
  const [params, setParams] = useSearchParams();
  const tipo = (params.get("tipo") as TipoRanking) || "categoria";
  const categoria = params.get("categoria") ?? "";
  const uf = params.get("uf") ?? "";
  const partido = params.get("partido") ?? "";
  // Média por deputado só faz sentido para grupos (UF e partido)
  const ordemPermitida = tipo === "uf" || tipo === "partido";
  const ordem = ordemPermitida && params.get("ordem") === "media" ? "media" : "total";

  const filtros = useApi((s) => api.filtros(s), []);
  const ranking = useApi(
    (s) => api.ranking({ tipo, categoria, uf, partido, ordem, limite: tipo === "deputado" ? 100 : 60 }, s),
    [tipo, categoria, uf, partido, ordem],
  );

  const mudar = (novos: Record<string, string>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(novos)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p);
  };

  const select = "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-marca-900">Rankings</h1>
        <p className="mt-1 text-slate-600">
          Quem gasta mais, e com o quê. Clique numa linha para ver os deputados daquela categoria, estado ou partido.
        </p>
      </div>

      {/* Abas */}
      <div role="tablist" className="flex flex-wrap gap-1 border-b border-slate-200">
        {ABAS.map((aba) => (
          <button
            key={aba.tipo}
            role="tab"
            aria-selected={tipo === aba.tipo}
            onClick={() => mudar({ tipo: aba.tipo, ordem: "" })}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tipo === aba.tipo ? "border-marca-600 text-marca-700" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {aba.rotulo}
          </button>
        ))}
      </div>

      {/* Filtros: numa linha só, acima do ranking */}
      <div className="flex flex-wrap items-center gap-2">
        {tipo !== "categoria" && (
          <select aria-label="Categoria" className={select} value={categoria} onChange={(e) => mudar({ categoria: e.target.value })}>
            <option value="">Todas as categorias</option>
            {filtros.dados?.categorias.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nome}
              </option>
            ))}
          </select>
        )}
        {tipo !== "uf" && (
          <select aria-label="Estado" className={select} value={uf} onChange={(e) => mudar({ uf: e.target.value })}>
            <option value="">Todos os estados</option>
            {filtros.dados?.ufs.map((u) => (
              <option key={u}>{u}</option>
            ))}
          </select>
        )}
        {tipo !== "partido" && (
          <select aria-label="Partido" className={select} value={partido} onChange={(e) => mudar({ partido: e.target.value })}>
            <option value="">Todos os partidos</option>
            {filtros.dados?.partidos.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        )}
        {ordemPermitida && (
          <select aria-label="Ordenar por" className={select} value={ordem} onChange={(e) => mudar({ ordem: e.target.value === "media" ? "media" : "" })}>
            <option value="total">Ordenar por total</option>
            <option value="media">Ordenar por média por deputado</option>
          </select>
        )}
        {(categoria || uf || partido) && (
          <button className="text-sm text-marca-700 hover:underline" onClick={() => mudar({ categoria: "", uf: "", partido: "" })}>
            Limpar filtros
          </button>
        )}
      </div>

      {ordemPermitida && (
        <p className="rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-600">
          {tipo === "uf"
            ? "Estados com mais deputados gastam mais no total. A média por deputado é a comparação mais justa e, mesmo assim, estados longe de Brasília tendem a gastar mais, porque a cota deles é maior (inclui passagens mais caras)."
            : "Partidos maiores gastam mais no total; a média por deputado compara partidos de tamanhos diferentes. O partido considerado é o atual de cada deputado."}
        </p>
      )}

      {ranking.carregando && <Carregando />}
      {ranking.erro && <Erro mensagem={ranking.erro} aoTentarDeNovo={ranking.recarregar} />}
      {ranking.dados && ranking.dados.itens.length === 0 && (
        <Vazio titulo="Nenhum gasto com esses filtros." detalhe="Tente remover algum filtro." />
      )}
      {ranking.dados && ranking.dados.itens.length > 0 && (
        <TabelaRanking
          itens={ranking.dados.itens}
          tipo={tipo}
          ordem={ordem}
          periodo={`${mesPorExtenso(ranking.dados.periodo.de)} a ${mesPorExtenso(ranking.dados.periodo.ate)}`}
          aoDetalhar={(item) => mudar({ tipo: "deputado", ordem: "", [tipo]: item.chave })}
        />
      )}
    </div>
  );
}

function TabelaRanking({
  itens,
  tipo,
  ordem,
  periodo,
  aoDetalhar,
}: {
  itens: ItemRanking[];
  tipo: TipoRanking;
  ordem: "total" | "media";
  periodo: string;
  aoDetalhar: (item: ItemRanking) => void;
}) {
  // A barrinha de cada linha é proporcional ao valor usado na ordenação.
  const valor = (i: ItemRanking) => (ordem === "media" ? i.media_por_deputado : i.total);
  const maximo = Math.max(...itens.map(valor), 1);
  const ehGrupo = tipo !== "deputado";

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <p className="mb-3 text-sm text-slate-500">Período: {periodo}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="w-10 py-2 font-medium">#</th>
              <th className="py-2 font-medium">{ABAS.find((a) => a.tipo === tipo)?.rotulo.replace("Por ", "").replace(/^./, (c) => c.toUpperCase())}</th>
              <th className="w-1/4 py-2 font-medium">
                <span className="sr-only">Proporção</span>
              </th>
              <th className="py-2 text-right font-medium">Total</th>
              {ehGrupo && <th className="py-2 text-right font-medium">Média por deputado</th>}
              {ehGrupo && <th className="py-2 text-right font-medium">Deputados</th>}
              <th className="py-2 text-right font-medium">Notas</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((item) => (
              <tr key={item.chave} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="py-2 tabular-nums text-slate-400">{item.posicao}</td>
                <td className="py-2 pr-3">
                  {tipo === "deputado" ? (
                    <Link to={`/deputados/${item.chave}`} className="flex items-center gap-2 hover:underline">
                      <FotoDeputado url={item.url_foto} nome={item.nome} tamanho="h-7 w-7" />
                      <span className="font-medium text-slate-800">{item.nome}</span>
                      <span className="text-slate-500">
                        {item.partido}-{item.uf}
                      </span>
                    </Link>
                  ) : (
                    <button onClick={() => aoDetalhar(item)} className="text-left font-medium text-slate-800 hover:underline">
                      {item.nome}
                    </button>
                  )}
                </td>
                <td className="py-2 pr-3">
                  <div className="h-2 rounded-full bg-slate-100" aria-hidden>
                    <div
                      className="h-2 rounded-full"
                      style={{ width: `${(valor(item) / maximo) * 100}%`, background: "var(--grafico-serie-1)" }}
                    />
                  </div>
                </td>
                <td className="py-2 text-right whitespace-nowrap tabular-nums">{moeda(item.total)}</td>
                {ehGrupo && <td className="py-2 text-right whitespace-nowrap tabular-nums">{moeda(item.media_por_deputado)}</td>}
                {ehGrupo && <td className="py-2 text-right tabular-nums">{numero(item.n_deputados)}</td>}
                <td className="py-2 text-right tabular-nums">{numero(item.n_notas)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
