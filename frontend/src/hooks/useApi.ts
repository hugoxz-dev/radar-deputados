import { useCallback, useEffect, useState } from "react";

import { ErroApi } from "../api/client";

// Hook genérico para buscar dados: devolve { dados, carregando, erro, recarregar }.
// Toda página usa este hook, por isso os três estados (carregando / erro / dados)
// são tratados de forma igual no site inteiro.
//
// O AbortController cancela a requisição anterior quando os parâmetros mudam
// (ex.: o usuário troca o filtro rápido). Sem isso, uma resposta antiga que
// chegasse depois poderia sobrescrever a nova.
export function useApi<T>(buscar: (signal: AbortSignal) => Promise<T>, deps: unknown[]) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [statusErro, setStatusErro] = useState<number | null>(null); // ex.: 404, 403
  const [carregando, setCarregando] = useState(true);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    const controle = new AbortController();
    setCarregando(true);
    setErro(null);
    setStatusErro(null);
    buscar(controle.signal)
      .then((resultado) => {
        setDados(resultado);
        setCarregando(false);
      })
      .catch((e: Error) => {
        if (e.name === "AbortError") return; // cancelada de propósito
        setErro(e.message);
        setStatusErro(e instanceof ErroApi ? e.status : null);
        setCarregando(false);
      });
    return () => controle.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tentativa]);

  const recarregar = useCallback(() => setTentativa((t) => t + 1), []);
  return { dados, carregando, erro, statusErro, recarregar };
}
