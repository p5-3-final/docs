// SPEC-034 성공 지표를 로컬 compose(media·auth 실제)에서 화면으로 확인한다.
// 세션 만들기 → 작업 전·후 영상 올리기 → 세션 상세의 역할별 표시 → 보존 설정 바꾸기.
import { expect, test } from "@playwright/test";

const CLIP = process.env.E2E_SHORT_VIDEO;

// 로그인 칸에 미리 채워지는 샘플 관리자 계정(local/.env의 AUTH_ADMIN_*)으로 그대로 로그인한다.
async function logInWithDefaultAccount(page) {
  await page.goto("/login");
  await expect(page.getByLabel("이메일")).not.toHaveValue("");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "영상 분석" })).toBeVisible();
}

test("[SPEC-034 성공 지표] 세션을 만들고 작업 전·후 영상을 올려 세션 상세에서 역할별로 본다", async ({ page }) => {
  await logInWithDefaultAccount(page);
  const name = `E2E 세션 ${Date.now()}`;
  await page.goto("/history");
  await page.getByRole("button", { name: "세션 만들기" }).first().click();
  const form = page.getByRole("form", { name: "세션 만들기" });
  await form.getByLabel("세션 이름").fill(name);
  await form.getByRole("button", { name: "만들기" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();

  await page.getByRole("link", { name: "이 세션에 영상 올리기" }).click();
  const queue = page.getByRole("list", { name: "업로드 대기열" });
  await page.getByRole("radio", { name: "작업 전" }).check();
  await page.getByLabel("영상 파일 고르기").setInputFiles({ name: "before.mp4", mimeType: "video/mp4", buffer: await readClip() });
  await expect(queue.getByText("업로드 완료")).toHaveCount(1, { timeout: 120_000 });
  await page.getByRole("radio", { name: "작업 후" }).check();
  await page.getByLabel("영상 파일 고르기").setInputFiles({ name: "after.mp4", mimeType: "video/mp4", buffer: await readClip() });
  await expect(queue.getByText("업로드 완료")).toHaveCount(2, { timeout: 120_000 });

  await page.goto("/history");
  await page.getByRole("link", { name }).click();
  await expect(page.getByRole("region", { name: "작업 전 영상" }).getByRole("link", { name: "before.mp4" })).toBeVisible();
  await expect(page.getByRole("region", { name: "작업 후 영상" }).getByRole("link", { name: "after.mp4" })).toBeVisible();
});

test("[SPEC-034 성공 지표] 설정 화면에서 학습용 보존 기본값을 바꾸고 되돌린다", async ({ page }) => {
  await logInWithDefaultAccount(page);
  await page.goto("/settings");
  const toggle = page.getByRole("switch", { name: "학습용 보존 기본 동의" });
  const before = await toggle.getAttribute("aria-checked");
  await toggle.click();
  await expect(page.getByText("이후에 올리는 영상에 적용됩니다.")).toBeVisible();
  await expect(toggle).not.toHaveAttribute("aria-checked", before);
  // 새로 고쳐도 서버(media)에 저장된 값이 보이는지 확인한 뒤 원래 값으로 되돌린다.
  await page.reload();
  await expect(toggle).not.toHaveAttribute("aria-checked", before);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", before);
});

async function readClip() {
  const { readFile } = await import("node:fs/promises");
  return readFile(CLIP);
}
