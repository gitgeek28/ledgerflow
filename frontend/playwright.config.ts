import { defineConfig } from "@playwright/test";

// Runs against the local dev stack (make dev). globalSetup resets the demo data to the standard baseline.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  workers: 1,
  globalSetup: "./e2e/global-setup.ts",
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure" },
  reporter: [["list"]],
});
