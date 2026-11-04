// Web build end-to-end tests (spec §16 E2E). Needs `npx expo export -p web` and the laptop services
// (ty-channels :8002, MCP :8001). Run: pnpm e2e:web
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e/web",
  timeout: 180_000,
  expect: { timeout: 60_000 },
  reporter: [["list"]],
  use: { baseURL: "http://localhost:8081", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: { command: "node e2e/web/serve.mjs", url: "http://localhost:8081", reuseExistingServer: true },
});
