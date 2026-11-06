import { defineConfig, devices } from "@playwright/test";

const APP = "http://localhost:3100";
const STUB = "http://localhost:4010";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: APP, locale: "tr-TR", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    { command: "node e2e/stub-server.mjs", url: `${STUB}/health`, reuseExistingServer: false },
    {
      // Üretim derlemesi sınanır: geliştirme sunucusu tamponlamayı ve CSP'yi farklı davranır.
      command: "npx next build && npx next start -p 3100",
      url: `${APP}/signed-out`,
      timeout: 240_000,
      reuseExistingServer: false,
      env: {
        APP_URL: APP,
        API_URL: STUB,
        OIDC_ISSUER: `${STUB}/realms/meridian`,
        OIDC_CLIENT_ID: "meridian-web",
        SESSION_SECRET: "e2e-only-secret-e2e-only-secret-e2e-only",
      },
    },
  ],
});
