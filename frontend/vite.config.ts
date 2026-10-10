import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// /api — на бэкенд (API_URL) или мок-сервис: `API_URL=http://localhost:8001 npm run dev`.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api/v1/storefront":
        process.env.STOREFRONT_URL ?? process.env.API_URL ?? "http://localhost:8000",
      "/api": process.env.API_URL ?? "http://localhost:8000",
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}", "mock-api/**/*.test.ts"],
  },
});
