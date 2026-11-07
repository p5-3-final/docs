import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { expect, test } from "@playwright/test";

// run.sh workers가 남긴 결과물 폴더
const OUT = resolve(process.env.E2E_OUT ?? new URL("../out", import.meta.url).pathname);

const ANALYZED = JSON.parse(readFileSync(`${OUT}/upload-result.json`, "utf8"));
const pause = (page, ms) => page.waitForTimeout(ms);

// 로그인 칸에 미리 채워지는 샘플 관리자 계정(local/.env의 AUTH_ADMIN_*)으로 그대로 로그인한다.
async function logInWithDefaultAccount(page) {
  await page.goto("/login");
  await expect(page.getByLabel("이메일")).not.toHaveValue("");
  await expect(page.getByLabel("비밀번호")).not.toHaveValue("");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "영상 분석" })).toBeVisible();
}


test("흐름 녹화: 기본 계정 로그인 → 분석한 영상 재생 → 워커 분석 결과", async ({ page }) => {
  await logInWithDefaultAccount(page);
  await pause(page, 1500);

  // 워커 결과와 같은 영상을 보여 주도록 upload 단계에서 올리고 분석한 영상을 연다.
  const list = page.getByRole("list", { name: "내 영상" });
  await list.locator(`a[href*="${ANALYZED.videoId}"]`).first().click();
  await expect(page.getByRole("heading", { name: "video.mp4" })).toBeVisible();
  const video = page.locator("video").first();
  await video.evaluate((v) => { v.muted = true; return v.play(); });
  await expect.poll(() => video.evaluate((v) => v.currentTime), { timeout: 60_000 }).toBeGreaterThan(6);
  await pause(page, 1500);

  // 웹 화면에는 분석 결과를 읽을 서비스가 아직 없어 워커 결과 페이지로 넘어간다.
  await page.goto(pathToFileURL(`${OUT}/results.html`).href);
  for (const section of await page.locator("section").all()) {
    await section.scrollIntoViewIfNeeded();
    if (await section.locator("video").count()) {
      await section.locator("video").evaluate((v) => v.play());
      await pause(page, 9000);
    } else {
      await pause(page, 4500);
    }
  }
});
