import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { expect, test } from "@playwright/test";

const VIDEO = process.env.E2E_VIDEO;
const FILER = "http://localhost:8888/buckets/vlm-media/";
// run.sh workers가 남긴 결과에서 워커 산출물 경로를 꺼내 저장소 화면으로 보여 준다.
const OUT = resolve(process.env.E2E_OUT ?? new URL("../out", import.meta.url).pathname);
const workers = readFileSync(`${OUT}/workers-result.txt`, "utf8");
const pick = (re) => workers.match(re)[0];
const CLIP = pick(/sources\/\S+\/clip\.mp4/);
const RESULT = pick(/sources\/\S+\/source-result\.json/);
const NORMALIZED_DIR = pick(/sources\/[^/]+\/normalizations\//);

const pause = (page, ms) => page.waitForTimeout(ms);

// 로그인 칸에 미리 채워지는 샘플 관리자 계정(local/.env의 AUTH_ADMIN_*)으로 그대로 로그인한다.
async function logInWithDefaultAccount(page) {
  await page.goto("/login");
  await expect(page.getByLabel("이메일")).not.toHaveValue("");
  await expect(page.getByLabel("비밀번호")).not.toHaveValue("");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "영상 분석" })).toBeVisible();
}


test("흐름 녹화: 기본 계정 로그인 → 업로드 → 변환 → 재생 → 워커 결과", async ({ page }) => {
  await logInWithDefaultAccount(page);
  await pause(page, 1500);

  await page.getByLabel("영상 파일 고르기").setInputFiles(VIDEO);
  await expect(page.getByText("업로드 완료").first()).toBeVisible({ timeout: 180_000 });
  await pause(page, 2000);
  const list = page.getByRole("list", { name: "내 영상" });
  await expect(async () => {
    await page.reload();
    // 같은 계정으로 여러 번 올리므로 맨 위(방금 올린 영상)만 본다. 이전 실행이 남긴 영상 상태와 무관하게 한다.
    await expect(list.getByRole("listitem").first().getByText("분석 준비됨")).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 300_000, intervals: [5_000] });
  await pause(page, 2000);

  await list.getByRole("link", { name: "video.mp4" }).first().click();
  await expect(page.getByRole("heading", { name: "video.mp4" })).toBeVisible();
  const video = page.locator("video").first();
  await video.evaluate((v) => { v.muted = true; return v.play(); });
  await expect.poll(() => video.evaluate((v) => v.currentTime), { timeout: 60_000 }).toBeGreaterThan(6);
  await pause(page, 1500);

  await page.goto(pathToFileURL(`${OUT}/results.html`).href);
  await pause(page, 3000);
  await page.mouse.wheel(0, 600);
  await pause(page, 4000);

  await page.goto(FILER + CLIP);
  await pause(page, 8000);
  await page.goto(FILER + RESULT);
  await pause(page, 5000);
  await page.goto(FILER + NORMALIZED_DIR);
  await pause(page, 4000);
});
