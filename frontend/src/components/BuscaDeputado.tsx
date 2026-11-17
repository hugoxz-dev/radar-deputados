import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, type DeputadoResumo } from "../api/client";
import FotoDeputado from "./FotoDeputado";

// Campo de busca com sugestões. Espera o usuário parar de digitar por 300 ms
// antes de chamar a API ("debounce"), para não disparar uma requisição por tecla.
export default function BuscaDeputado() {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<DeputadoResumo[]>([]);
  const [estado, setEstado] = useState<"parado" | "buscando" | "erro">("parado");
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0); // item destacado pelo teclado
  const navegar = useNavigate();
  const caixa = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const termo = texto.trim();
    if (termo.length < 2) {
      setResultados([]);
      setEstado("parado");
      return;
    }
    const controle = new AbortController();
    const espera = setTimeout(() => {
      setEstado("buscando");
      api
        .deputados({ busca: termo, itens: 8 }, controle.signal)
        .then((r) => {
          setResultados(r.itens);
          setAtivo(0);
          setEstado("parado");
        })
        .catch((e: Error) => e.name !== "AbortError" && setEstado("erro"));
    }, 300);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [texto]);

  // Fecha a lista ao clicar fora
  useEffect(() => {
    const fechar = (e: MouseEvent) => {
      if (!caixa.current?.contains(e.target as Node)) setAberto(false);
    };
    document.addEventListener("mousedown", fechar);
    return () => document.removeEventListener("mousedown", fechar);
  }, []);

  const abrirPerfil = (d: DeputadoResumo) => {
    setAberto(false);
    setTexto("");
    navegar(`/deputados/${d.id}`);
  };

  const aoTeclar = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") setAtivo((a) => Math.min(a + 1, resultados.length - 1));
    else if (e.key === "ArrowUp") setAtivo((a) => Math.max(a - 1, 0));
    else if (e.key === "Enter" && resultados[ativo]) abrirPerfil(resultados[ativo]);
    else if (e.key === "Escape") setAberto(false);
  };

  const mostrarLista = aberto && texto.trim().length >= 2;

  return (
    <div ref={caixa} className="relative w-full max-w-xl">
      <label htmlFor="busca-deputado" className="sr-only">
        Buscar deputado pelo nome
      </label>
      <input
        id="busca-deputado"
        type="search"
        autoComplete="off"
        placeholder="Buscar deputado pelo nome…"
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value);
          setAberto(true);
        }}
        onFocus={() => setAberto(true)}
        onKeyDown={aoTeclar}
        role="combobox"
        aria-expanded={mostrarLista}
        aria-controls="lista-busca"
        className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-base shadow-sm outline-none focus:border-marca-600 focus:ring-2 focus:ring-marca-100"
      />
      {mostrarLista && (
        <ul id="lista-busca" role="listbox" className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
          {estado === "buscando" && <li className="px-4 py-3 text-sm text-slate-500">Buscando…</li>}
          {estado === "erro" && <li className="px-4 py-3 text-sm text-red-700">Erro ao buscar. Tente de novo.</li>}
          {estado === "parado" && resultados.length === 0 && (
            <li className="px-4 py-3 text-sm text-slate-500">Nenhum deputado encontrado com “{texto.trim()}”.</li>
          )}
          {estado === "parado" &&
            resultados.map((d, i) => (
              <li
                key={d.id}
                role="option"
                aria-selected={i === ativo}
                onMouseEnter={() => setAtivo(i)}
                onMouseDown={() => abrirPerfil(d)}
                className={`flex cursor-pointer items-center gap-3 px-4 py-2 ${i === ativo ? "bg-marca-50" : ""}`}
              >
                <FotoDeputado url={d.url_foto} nome={d.nome} tamanho="h-9 w-9" />
                <span className="font-medium text-slate-800">{d.nome}</span>
                <span className="text-sm text-slate-500">
                  {d.partido}-{d.uf}
                  {!d.em_exercicio && " · fora do exercício"}
                </span>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
