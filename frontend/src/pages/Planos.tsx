import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Carregando, Erro } from "../components/Estado";
import { useApi } from "../hooks/useApi";
import { moeda } from "../lib/formato";

export default function Planos() {
  const planos = useApi((s) => api.planos(s), []);
  const { usuario, recarregar } = useAuth();
  const navegar = useNavigate();
  const [params] = useSearchParams();
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const assinar = async () => {
    // Sem conta: cria a conta primeiro e volta para cá
    if (!usuario) {
      navegar(`/cadastro?proximo=${encodeURIComponent("/planos")}`);
      return;
    }
    setEnviando(true);
    setErro(null);
    try {
      const r = await api.assinar();
      if (r.checkout_url) {
        window.location.href = r.checkout_url; // Stripe: paga lá e volta para /minha-conta
        return;
      }
      await recarregar(); // simulado: já é Pro
      navegar("/minha-conta?assinatura=sucesso");
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  if (planos.carregando) return <Carregando />;
  if (planos.erro || !planos.dados) return <Erro mensagem={planos.erro ?? ""} aoTentarDeNovo={planos.recarregar} />;
  const { modo_pagamento } = planos.dados;

  return (
    <div className="space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-marca-900">Planos</h1>
        <p className="mx-auto mt-2 max-w-2xl text-slate-600">
          O painel é público e gratuito. O plano Pro é para quem acompanha os gastos de perto: jornalistas, assessorias e
          pesquisadores.
        </p>
      </div>

      {params.get("assinatura") === "cancelada" && (
        <p className="mx-auto max-w-xl rounded-md bg-slate-100 px-4 py-3 text-center text-sm text-slate-700">
          O pagamento não foi concluído. Você pode tentar de novo quando quiser.
        </p>
      )}

      <div className="mx-auto grid max-w-4xl grid-cols-1 gap-6 md:grid-cols-2">
        {planos.dados.planos.map((plano) => {
          const pro = plano.id === "pro";
          const atual = usuario?.plano === plano.id || (!usuario && plano.id === "free");
          return (
            <section
              key={plano.id}
              className={`flex flex-col rounded-lg border bg-white p-6 shadow-sm ${pro ? "border-marca-600 ring-2 ring-marca-100" : "border-slate-200"}`}
            >
              <h2 className="text-xl font-semibold text-slate-900">{plano.nome}</h2>
              <p className="mt-2">
                <span className="text-3xl font-bold text-slate-900">{plano.preco_mensal ? moeda(plano.preco_mensal) : "R$ 0"}</span>
                <span className="text-slate-500"> /mês</span>
              </p>
              <ul className="mt-5 flex-1 space-y-2 text-slate-700">
                {plano.recursos.map((r) => (
                  <li key={r} className="flex gap-2">
                    <span aria-hidden className="text-marca-600">✓</span>
                    {r}
                  </li>
                ))}
              </ul>
              <div className="mt-6">
                {pro && usuario?.plano !== "pro" && (
                  <button
                    onClick={assinar}
                    disabled={enviando}
                    className="w-full rounded-md bg-marca-700 px-4 py-2.5 font-medium text-white hover:bg-marca-900 disabled:opacity-60"
                  >
                    {enviando ? "Processando…" : usuario ? "Assinar o Pro" : "Criar conta e assinar"}
                  </button>
                )}
                {atual && <p className="text-center text-sm font-medium text-slate-500">Seu plano atual</p>}
              </div>
            </section>
          );
        })}
      </div>

      {erro && (
        <p role="alert" className="mx-auto max-w-xl rounded-md bg-red-50 px-4 py-3 text-center text-sm text-red-800">
          {erro}
        </p>
      )}

      {modo_pagamento === "simulado" && (
        <p className="mx-auto max-w-2xl text-center text-sm text-slate-500">
          Ambiente de demonstração: o pagamento está no <strong>modo simulado</strong>. Assinar ativa o Pro na hora, por 30
          dias, sem cobrança.
        </p>
      )}
    </div>
  );
}
