import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3100", headless: true },
  reporter: "list",
  timeout: 60000,
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: "pnpm start --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100/ask",
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
});
