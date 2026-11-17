import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const LINKS = [
  { para: "/", rotulo: "Início" },
  { para: "/rankings", rotulo: "Rankings" },
  { para: "/alertas", rotulo: "Fora do padrão" },
  { para: "/metodologia", rotulo: "Metodologia" },
  { para: "/planos", rotulo: "Planos" },
];

// Canto direito do cabeçalho: "Entrar" para visitantes; nome + selo Pro + "Sair" para quem está logado.
function AreaConta() {
  const { usuario, carregando, sair } = useAuth();
  const navegar = useNavigate();
  if (carregando) return null;
  if (!usuario) {
    return (
      <Link to="/login" className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-marca-900 hover:bg-marca-50">
        Entrar
      </Link>
    );
  }
  return (
    <div className="flex items-center gap-2 text-sm">
      <Link to="/minha-conta" className="rounded-md px-2 py-1.5 text-white hover:bg-white/10">
        {usuario.nome.split(" ")[0]}
        {usuario.plano === "pro" && (
          <span className="ml-1.5 rounded bg-marca-100 px-1.5 py-0.5 text-xs font-semibold text-marca-900">PRO</span>
        )}
      </Link>
      <button
        onClick={() => {
          sair();
          navegar("/");
        }}
        className="rounded-md px-2 py-1.5 text-marca-100 hover:bg-white/10"
      >
        Sair
      </button>
    </div>
  );
}

// Estrutura comum a todas as páginas: cabeçalho, conteúdo (Outlet) e rodapé.
export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="bg-marca-900 text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            <span aria-hidden className="inline-block h-3 w-3 rounded-full bg-marca-100 ring-4 ring-marca-600" />
            Radar dos Deputados
          </Link>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <nav className="flex flex-wrap gap-1 text-sm">
            {LINKS.map((l) => (
              <NavLink
                key={l.para}
                to={l.para}
                end={l.para === "/"}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 ${isActive ? "bg-white/15 font-medium text-white" : "text-marca-100 hover:bg-white/10"}`
                }
              >
                {l.rotulo}
              </NavLink>
            ))}
          </nav>
          <AreaConta />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl space-y-1 px-4 py-6 text-sm text-slate-600">
          <p>
            Fonte: API de Dados Abertos da Câmara dos Deputados. Os destaques de gasto fora do padrão são estatísticos:{" "}
            <strong>um gasto atípico não significa ilegalidade</strong>.{" "}
            <Link to="/metodologia" className="text-marca-700 hover:underline">
              Veja a metodologia
            </Link>
            .
          </p>
          <p className="text-slate-500">Projeto pessoal, sem vínculo com a Câmara dos Deputados.</p>
        </div>
      </footer>
    </div>
  );
}
