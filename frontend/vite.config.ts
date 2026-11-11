import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento (npm run dev) a tela roda na 5173 e repassa /api para o backend na 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000", "/pronto": "http://127.0.0.1:8000" },
  },
});
