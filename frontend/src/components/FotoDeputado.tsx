import { useState } from "react";

// Foto oficial da Câmara; se não carregar, mostra as iniciais.
export default function FotoDeputado({ url, nome, tamanho = "h-12 w-12" }: { url: string | null; nome: string; tamanho?: string }) {
  const [falhou, setFalhou] = useState(false);
  const iniciais = nome
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();

  if (!url || falhou) {
    return (
      <div className={`${tamanho} flex shrink-0 items-center justify-center rounded-full bg-marca-100 font-semibold text-marca-700`} aria-hidden>
        {iniciais}
      </div>
    );
  }
  return (
    <img
      src={url}
      alt={`Foto de ${nome}`}
      loading="lazy"
      onError={() => setFalhou(true)}
      className={`${tamanho} shrink-0 rounded-full bg-slate-200 object-cover object-top`}
    />
  );
}
