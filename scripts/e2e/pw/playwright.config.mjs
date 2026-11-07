// 로컬 compose E2E: 실제 api-gateway에 붙은 frontend(localhost:3000)를 확인한다.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "smoke.spec.mjs",
  outputDir: `${process.env.E2E_OUT ?? "../out"}/pw-results`,
  workers: 1,
  timeout: 300_000,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
  projects: [{ name: "desktop", use: { ...devices["Desktop Chrome"] } }],
});
