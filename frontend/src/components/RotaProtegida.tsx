import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Carregando } from "./Estado";

// Envolve páginas que exigem login: sem usuário, manda para /login e volta depois.
export default function RotaProtegida({ children }: { children: ReactNode }) {
  const { usuario, carregando } = useAuth();
  const local = useLocation();
  if (carregando) return <Carregando />;
  if (!usuario) return <Navigate to={`/login?proximo=${encodeURIComponent(local.pathname + local.search)}`} replace />;
  return <>{children}</>;
}
