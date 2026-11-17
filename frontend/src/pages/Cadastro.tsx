import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { CartaoConta, estiloBotao, estiloCampo } from "./Login";

export default function Cadastro() {
  const { cadastrar } = useAuth();
  const navegar = useNavigate();
  const [params] = useSearchParams();
  const proximo = params.get("proximo") ?? "/minha-conta";
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await cadastrar(nome, email, senha);
      navegar(proximo);
    } catch (falha) {
      setErro((falha as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <CartaoConta titulo="Criar conta">
      <p className="-mt-3 mb-5 text-sm text-slate-600">A conta é grátis. O plano Pro pode ser assinado depois.</p>
      <form onSubmit={enviar} className="space-y-4">
        <label className="block text-sm font-medium text-slate-700">
          Nome
          <input required minLength={2} autoComplete="name" className={estiloCampo} value={nome} onChange={(e) => setNome(e.target.value)} />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          E-mail
          <input type="email" required autoComplete="email" className={estiloCampo} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Senha
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            className={estiloCampo}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
          <span className="mt-1 block text-xs font-normal text-slate-500">Mínimo de 8 caracteres.</span>
        </label>
        {erro && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
            {erro}
          </p>
        )}
        <button type="submit" disabled={enviando} className={estiloBotao}>
          {enviando ? "Criando…" : "Criar conta"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        Já tem conta?{" "}
        <Link to={`/login?proximo=${encodeURIComponent(proximo)}`} className="font-medium text-marca-700 hover:underline">
          Entrar
        </Link>
      </p>
    </CartaoConta>
  );
}
