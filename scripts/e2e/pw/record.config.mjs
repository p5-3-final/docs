// 흐름 녹화용: 영상 녹화를 켜고 동작을 느리게 해서 화면 전환이 보이게 한다.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "record.spec.mjs",
  workers: 1,
  timeout: 600_000,
  outputDir: `${process.env.E2E_OUT ?? "../out"}/recording`,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://localhost:3000",
    viewport: { width: 1280, height: 720 },
    video: { mode: "on", size: { width: 1280, height: 720 } },
    launchOptions: { slowMo: 400 },
  },
});
