import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* BrowserRouter habilita as rotas (/deputados/123, /rankings...) sem recarregar a página */}
    <BrowserRouter>
      {/* AuthProvider: guarda quem está logado e deixa disponível para o site todo */}
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
