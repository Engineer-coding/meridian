import { defineConfig, devices } from "@playwright/test";
import { readFileSync } from "node:fs";

// Tam sistem: gerçek Keycloak, çekirdek API, AI servisi, RabbitMQ ve PostgreSQL (make e2e-full).
// Portlar geliştirme ortamından ayrıdır; altyapı infra/compose/compose.e2e.yaml ile kurulur.
const APP = "http://localhost:3200";
const API = "http://localhost:18080";
const AI_PORT = "18090";
const ISSUER = "http://localhost:18180/realms/meridian";
// İzler gerçekten toplanır: test, tek bir sorunun üç servisten geçen tek iz bıraktığını Tempo'dan okur.
const TELEMETRY = { OTEL_EXPORT: "true", OTEL_ENDPOINT: "http://127.0.0.1:14318", DEPLOYMENT_ENVIRONMENT: "e2e" };

const secrets = Object.fromEntries(
  readFileSync(new URL("../../.env.example", import.meta.url), "utf8")
    .split(/\r?\n/)
    .filter((line) => line.includes("=") && !line.startsWith("#"))
    .map((line) => line.split("=", 2) as [string, string]),
);

export default defineConfig({
  testDir: "./e2e-full",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 120_000,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: APP, locale: "tr-TR", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "java -jar target/api-0.0.1-SNAPSHOT.jar",
      cwd: "../api",
      url: `${API}/actuator/health/readiness`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...secrets,
        ...TELEMETRY,
        SERVER_PORT: "18080",
        SPRING_DATASOURCE_URL: "jdbc:postgresql://localhost:15432/meridian",
        SPRING_RABBITMQ_PORT: "15673",
        SPRING_DATA_REDIS_PORT: "16379",
        SPRING_SECURITY_OAUTH2_RESOURCESERVER_JWT_ISSUER_URI: ISSUER,
        MERIDIAN_AI_URL: `http://127.0.0.1:${AI_PORT}`,
      },
    },
    {
      command: "uv run python tests/e2e_stack.py",
      cwd: "../ai-service",
      url: `http://127.0.0.1:${AI_PORT}/health/ready`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...secrets,
        ...TELEMETRY,
        PYTHONUTF8: "1",
        HTTP_PORT: AI_PORT,
        POSTGRES_PORT: "15432",
        RABBITMQ_PORT: "15673",
        API_URL: API,
      },
    },
    {
      command: "npx next build && npx next start -p 3200",
      url: `${APP}/signed-out`,
      timeout: 240_000,
      reuseExistingServer: false,
      env: {
        ...TELEMETRY,
        APP_URL: APP,
        API_URL: API,
        OIDC_ISSUER: ISSUER,
        OIDC_CLIENT_ID: "meridian-web",
        SESSION_SECRET: "e2e-only-secret-e2e-only-secret-e2e-only",
      },
    },
  ],
});
