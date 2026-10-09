import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// /api — на бэкенд (API_URL) или мок-сервис: `API_URL=http://localhost:8001 npm run dev`.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": process.env.API_URL ?? "http://localhost:8000" },
  },
  test: { environment: "node" },
});
