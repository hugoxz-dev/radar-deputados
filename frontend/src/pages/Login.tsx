import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

// Usado por Login e Cadastro: mesmo visual, campos diferentes.
export function CartaoConta({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <h1 className="mb-6 text-2xl font-bold text-marca-900">{titulo}</h1>
      {children}
    </div>
  );
}

export const estiloCampo =
  "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-marca-600 focus:ring-2 focus:ring-marca-100";
export const estiloBotao =
  "w-full rounded-md bg-marca-700 px-4 py-2.5 font-medium text-white hover:bg-marca-900 disabled:opacity-60";

export default function Login() {
  const { entrar } = useAuth();
  const navegar = useNavigate();
  const [params] = useSearchParams();
  const proximo = params.get("proximo") ?? "/minha-conta"; // para onde ir depois de entrar
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email, senha);
      navegar(proximo);
    } catch (falha) {
      setErro((falha as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <CartaoConta titulo="Entrar">
      <form onSubmit={enviar} className="space-y-4">
        <label className="block text-sm font-medium text-slate-700">
          E-mail
          <input type="email" required autoComplete="email" className={estiloCampo} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Senha
          <input type="password" required autoComplete="current-password" className={estiloCampo} value={senha} onChange={(e) => setSenha(e.target.value)} />
        </label>
        {erro && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
            {erro}
          </p>
        )}
        <button type="submit" disabled={enviando} className={estiloBotao}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        Ainda não tem conta?{" "}
        <Link to={`/cadastro?proximo=${encodeURIComponent(proximo)}`} className="font-medium text-marca-700 hover:underline">
          Criar conta grátis
        </Link>
      </p>
    </CartaoConta>
  );
}
