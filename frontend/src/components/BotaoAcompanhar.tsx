import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { api, type Inscricao } from "../api/client";
import { useAuth } from "../auth/AuthContext";

// Botão "Acompanhar" do perfil: recebe e-mail quando surgir gasto fora do padrão deste deputado.
// - visitante: leva para o login;
// - plano grátis: explica que é recurso Pro;
// - Pro: liga/desliga a inscrição.
export default function BotaoAcompanhar({ deputadoId }: { deputadoId: number }) {
  const { usuario } = useAuth();
  const local = useLocation();
  const [inscricao, setInscricao] = useState<Inscricao | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const pro = usuario?.plano === "pro";

  useEffect(() => {
    if (!pro) return;
    const controle = new AbortController();
    api
      .inscricoes(controle.signal)
      .then((lista) => setInscricao(lista.find((i) => i.tipo === "deputado" && i.valor === String(deputadoId)) ?? null))
      .catch(() => undefined);
    return () => controle.abort();
  }, [pro, deputadoId]);

  const estilo = "rounded-md px-3 py-1.5 text-sm font-medium ring-1";

  if (!usuario) {
    return (
      <Link to={`/login?proximo=${encodeURIComponent(local.pathname)}`} className={`${estilo} text-marca-700 ring-marca-100 hover:bg-marca-50`}>
        Acompanhar
      </Link>
    );
  }
  if (!pro) {
    return (
      <Link to="/planos" className={`${estilo} text-marca-700 ring-marca-100 hover:bg-marca-50`} title="Recurso do plano Pro">
        Acompanhar <span className="ml-1 rounded bg-marca-100 px-1 text-xs">PRO</span>
      </Link>
    );
  }

  const alternar = async () => {
    setOcupado(true);
    setErro(null);
    try {
      if (inscricao) {
        await api.removerInscricao(inscricao.id);
        setInscricao(null);
      } else {
        setInscricao(await api.criarInscricao("deputado", String(deputadoId)));
      }
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        onClick={alternar}
        disabled={ocupado}
        aria-pressed={inscricao !== null}
        className={`${estilo} disabled:opacity-60 ${
          inscricao ? "bg-marca-700 text-white ring-marca-700 hover:bg-marca-900" : "text-marca-700 ring-marca-100 hover:bg-marca-50"
        }`}
      >
        {inscricao ? "✓ Acompanhando" : "Acompanhar"}
      </button>
      <span className="text-xs text-slate-500">
        {inscricao ? "Você recebe e-mail com novos gastos fora do padrão." : "Receba e-mail com novos gastos fora do padrão."}
      </span>
      {erro && <span className="text-xs text-red-700">{erro}</span>}
    </div>
  );
}
