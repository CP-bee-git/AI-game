import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 60_000,
  use: { baseURL: "http://localhost:3005", headless: true },
  webServer: [
    {
      command: "../.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8020",
      url: "http://127.0.0.1:8020/api/v1/health",
      timeout: 120_000,
      env: {
        LOCAL_STORAGE_DIR: "/tmp/careerpilot-e2e-storage/uploads",
        STATE_DB_PATH: "/tmp/careerpilot-e2e-storage/state.sqlite3",
        AI_BACKEND: "legacy",
        DASHSCOPE_API_KEY: "",
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: process.env.CI ? "pnpm build && pnpm start --hostname localhost --port 3005" : "pnpm dev --hostname localhost --port 3005",
      env: { API_INTERNAL_URL: "http://127.0.0.1:8020", CAREERPILOT_TEST_BUILD: "1" },
      url: "http://localhost:3005",
      timeout: 180_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
