import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const siteUrl = (process.env.SITE_URL ?? "").replace(/\/+$/, "");
const ragUrl = process.env.RAG_API_URL ?? "http://127.0.0.1:8100";

function siteUrlPlugin(): Plugin {
  return {
    name: "site-url",
    transformIndexHtml: (html) => html.replaceAll("%SITE_URL%", siteUrl),
  };
}

export default defineConfig({
  plugins: [react(), siteUrlPlugin()],
  server: {
    proxy: {
      "/rag": {
        target: ragUrl,
        rewrite: (path) => path.replace(/^\/rag/, ""),
        timeout: 180000,
        proxyTimeout: 180000,
      },
    },
  },
  preview: {
    proxy: {
      "/rag": { target: ragUrl, rewrite: (path) => path.replace(/^\/rag/, "") },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
