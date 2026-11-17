import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Para onde o Vite repassa as chamadas /api/*.
// Fora do Docker: a API roda em localhost:8000. No Docker: o compose define http://api:8000.
const alvoApi = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // aceita conexões de fora do container
    port: 5173,
    // No Windows + Docker, o hot-reload só funciona com polling.
    watch: { usePolling: process.env.VITE_USE_POLLING === "true" },
    // Proxy: o navegador chama /api/deputados e o Vite encaminha para a API em /deputados.
    // Assim front e API parecem estar na mesma origem e evitamos problemas de CORS.
    proxy: {
      "/api": {
        target: alvoApi,
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ""),
      },
    },
  },
});
