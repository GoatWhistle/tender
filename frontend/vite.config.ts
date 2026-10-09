import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// VITE_API=http — запросы к бэкенду через прокси; по умолчанию мок в браузере.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": process.env.API_URL ?? "http://localhost:8000" },
  },
  test: { environment: "node" },
});
