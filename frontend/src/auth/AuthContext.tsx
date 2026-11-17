import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { api, EVENTO_SESSAO_EXPIRADA, lerToken, salvarToken, type Usuario } from "../api/client";

// Contexto de login: qualquer componente sabe quem está logado com useAuth(),
// sem precisar passar o usuário de pai para filho.
type Auth = {
  usuario: Usuario | null;
  carregando: boolean; // true enquanto confere o token salvo, ao abrir o site
  entrar: (email: string, senha: string) => Promise<void>;
  cadastrar: (nome: string, email: string, senha: string) => Promise<void>;
  sair: () => void;
  recarregar: () => Promise<void>; // relê /auth/me (ex.: depois de assinar)
};

const ContextoAuth = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  const recarregar = useCallback(async () => {
    if (!lerToken()) {
      setUsuario(null);
      return;
    }
    try {
      setUsuario(await api.me());
    } catch {
      setUsuario(null); // token inválido/expirado: o client já apagou
    }
  }, []);

  // Ao abrir o site: se há token salvo, descobre de quem é
  useEffect(() => {
    recarregar().finally(() => setCarregando(false));
    const expirou = () => setUsuario(null);
    window.addEventListener(EVENTO_SESSAO_EXPIRADA, expirou);
    return () => window.removeEventListener(EVENTO_SESSAO_EXPIRADA, expirou);
  }, [recarregar]);

  const entrar = async (email: string, senha: string) => {
    const r = await api.login({ email, senha });
    salvarToken(r.access_token);
    setUsuario(r.usuario);
  };

  const cadastrar = async (nome: string, email: string, senha: string) => {
    const r = await api.cadastro({ nome, email, senha });
    salvarToken(r.access_token);
    setUsuario(r.usuario);
  };

  const sair = () => {
    salvarToken(null);
    setUsuario(null);
  };

  return (
    <ContextoAuth.Provider value={{ usuario, carregando, entrar, cadastrar, sair, recarregar }}>{children}</ContextoAuth.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): Auth {
  const contexto = useContext(ContextoAuth);
  if (!contexto) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return contexto;
}
