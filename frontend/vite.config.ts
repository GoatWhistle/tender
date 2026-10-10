import { fileURLToPath, URL } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import svgr from "vite-plugin-svgr"

export default defineConfig({
  plugins: [react(), svgr()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.RAG_API_URL ?? "http://127.0.0.1:8100",
        rewrite: (path) => path.replace(/^\/api/, ""),
        timeout: 180000,
        proxyTimeout: 180000,
      },
    },
  },
})
