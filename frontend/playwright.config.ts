import { defineConfig } from "@playwright/test"
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  use: {
    channel: "chrome",
    baseURL: "http://127.0.0.1:5175",
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "cd .. && uv run rag-api",
      url: "http://127.0.0.1:8100/openapi.json",
      reuseExistingServer: true,
    },
    {
      command: "npm run dev -- --port 5175",
      url: "http://127.0.0.1:5175",
      reuseExistingServer: true,
    },
  ],
})
