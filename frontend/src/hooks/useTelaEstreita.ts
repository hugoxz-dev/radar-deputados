import { useEffect, useState } from "react";

// true em telas de celular (< 640px). Usado por gráficos que precisam
// encolher rótulos em vez de apenas encolher as barras.
export function useTelaEstreita(): boolean {
  const consulta = "(max-width: 639px)";
  const [estreita, setEstreita] = useState(() => window.matchMedia(consulta).matches);
  useEffect(() => {
    const mq = window.matchMedia(consulta);
    const aoMudar = () => setEstreita(mq.matches);
    mq.addEventListener("change", aoMudar);
    return () => mq.removeEventListener("change", aoMudar);
  }, []);
  return estreita;
}
