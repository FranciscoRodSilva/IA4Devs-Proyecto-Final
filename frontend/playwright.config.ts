import { defineConfig, devices } from "@playwright/test";

/**
 * Humo de TKT-008 (CA-14): contra el backend y la base reales.
 * Requisitos previos, no automatizados: `docker compose up -d db`, `alembic upgrade head`,
 * `herramientas.contrasenas_roles` y `npx playwright install chromium`.
 * El usuario de humo se siembra en `globalSetup` (`e2e/preparacion-global.ts`).
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/preparacion-global.ts",
  workers: 1,
  retries: 0,
  use: { baseURL: "http://localhost:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run --locked --env-file ../.env fastapi run --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/openapi.json",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true, timeout: 60_000 },
  ],
});
