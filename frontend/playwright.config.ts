import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 60_000,
  use: { baseURL: "http://localhost:3000", headless: true },
  webServer: [
    {
      command: "../.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health",
      timeout: 120_000,
      env: {
        LOCAL_STORAGE_DIR: "/tmp/careerpilot-e2e-storage/uploads",
        STATE_DB_PATH: "/tmp/careerpilot-e2e-storage/state.sqlite3",
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm dev --hostname localhost",
      url: "http://localhost:3000",
      timeout: 180_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
