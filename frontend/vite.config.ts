import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const siteUrl = (process.env.SITE_URL ?? "").replace(/\/+$/, "");

function siteUrlPlugin(): Plugin {
  return {
    name: "site-url",
    transformIndexHtml: (html) => html.replaceAll("%SITE_URL%", siteUrl),
  };
}

// /api — на бэкенд (API_URL) или мок-сервис: `API_URL=http://localhost:8001 npm run dev`.
export default defineConfig({
  plugins: [react(), siteUrlPlugin()],
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
