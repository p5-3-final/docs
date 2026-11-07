import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "@playwright/test";

// run.sh full이 남긴 결과물 폴더
const OUT = resolve(process.env.E2E_OUT ?? new URL("../out", import.meta.url).pathname);
const pause = (page, ms) => page.waitForTimeout(ms);

test("전체 영상 녹화: 검색어별 유사도 곡선과 상위 3구간 주석 클립", async ({ page }) => {
  await page.goto(pathToFileURL(`${OUT}/fullvideo.html`).href);
  await pause(page, 3000);
  for (const section of await page.locator("section").all()) {
    await section.scrollIntoViewIfNeeded();
    await pause(page, 2500);
    // 상위 3구간 클립을 함께 재생한다(각 10초).
    for (const video of await section.locator("video").all()) {
      await video.evaluate((v) => v.play());
    }
    await pause(page, 10_500);
  }
});
