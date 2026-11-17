import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";

import Layout from "./components/Layout";
import RotaProtegida from "./components/RotaProtegida";
import Alertas from "./pages/Alertas";
import Cadastro from "./pages/Cadastro";
import Deputado from "./pages/Deputado";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Metodologia from "./pages/Metodologia";
import MinhaConta from "./pages/MinhaConta";
import NaoEncontrada from "./pages/NaoEncontrada";
import Planos from "./pages/Planos";
import Rankings from "./pages/Rankings";

// Tabela de rotas do site.
export default function App() {
  const { pathname } = useLocation();
  // Ao trocar de página, volta ao topo (o React Router não faz isso sozinho).
  // Chaves de propósito: em navegadores novos scrollTo() devolve uma Promise, e o
  // useEffect só pode devolver uma função de limpeza (ou nada).
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="deputados/:id" element={<Deputado />} />
        <Route path="rankings" element={<Rankings />} />
        <Route path="alertas" element={<Alertas />} />
        <Route path="metodologia" element={<Metodologia />} />
        <Route path="planos" element={<Planos />} />
        <Route path="login" element={<Login />} />
        <Route path="cadastro" element={<Cadastro />} />
        <Route
          path="minha-conta"
          element={
            <RotaProtegida>
              <MinhaConta />
            </RotaProtegida>
          }
        />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  );
}
