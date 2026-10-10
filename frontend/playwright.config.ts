import { defineConfig, devices } from "@playwright/test";

const PORT = 5180;
const MOCK_PORT = 8011;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: "ru-RU",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `node mock-api/server.ts`,
      env: { MOCK_PORT: String(MOCK_PORT) },
      url: `http://127.0.0.1:${MOCK_PORT}/api/v1/storefront/categories`,
      reuseExistingServer: false,
    },
    {
      command: `npx vite --port ${PORT} --strictPort --host 127.0.0.1`,
      env: {
        STOREFRONT_URL: `http://127.0.0.1:${MOCK_PORT}`,
        API_URL: "http://127.0.0.1:9",
      },
      url: `http://127.0.0.1:${PORT}`,
      reuseExistingServer: false,
    },
  ],
});
