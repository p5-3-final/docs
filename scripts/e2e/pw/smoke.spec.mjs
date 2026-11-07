import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";

const VIDEO = process.env.E2E_VIDEO;
const OUT = process.env.E2E_OUT ?? new URL("../out", import.meta.url).pathname;
const PASSWORD = "E2eUser1234";

async function signUpAndLogIn(page, role) {
  const email = `e2e-ui-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("닉네임").fill("e2e");
  await page.getByLabel("비밀번호").fill(PASSWORD);
  const signedUp = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/signup"));
  await page.getByRole("button", { name: "가입하기" }).click();
  expect((await signedUp).status()).toBe(201);
  if (role) {
    // auth에 역할 변경 API가 없어 로컬 auth DB를 직접 바꾼다.
    execFileSync("docker", ["exec", "vlm-postgres-1", "psql", "-U", "postgres", "-d", "auth_db", "-qc",
      `UPDATE users SET role = '${role}' WHERE email = '${email}'`]);
  }
  await page.goto("/login");
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "영상 분석" })).toBeVisible();
}

// 로그인 칸에 미리 채워지는 샘플 관리자 계정(local/.env의 AUTH_ADMIN_*)으로 그대로 로그인한다.
async function logInWithDefaultAccount(page) {
  await page.goto("/login");
  await expect(page.getByLabel("이메일")).not.toHaveValue("");
  await expect(page.getByLabel("비밀번호")).not.toHaveValue("");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "영상 분석" })).toBeVisible();
}

test("로그인 → 화면에서 실제 영상 업로드 → 변환 완료 → 상세 재생", async ({ page }) => {
  await logInWithDefaultAccount(page);
  await page.getByLabel("영상 파일 고르기").setInputFiles(VIDEO);
  // 목록의 상태 표시와 섞이지 않게 업로드 대기열 안에서 본다. 끝나기 전에 새로 고치면 업로드가 끊긴다.
  await expect(page.getByRole("list", { name: "업로드 대기열" }).getByText("업로드 완료")).toBeVisible({ timeout: 300_000 });
  const list = page.getByRole("list", { name: "내 영상" });
  // 목록은 정규화 완료 알림을 받지 않아(spec에 요구 없음) 새로 고쳐 상태를 확인한다.
  await expect(async () => {
    await page.reload();
    // 같은 계정으로 여러 번 올리므로 맨 위(방금 올린 영상)만 본다. 이전 실행이 남긴 영상 상태와 무관하게 한다.
    await expect(list.getByRole("listitem").first().getByText("분석 준비됨")).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 180_000 });
  await list.getByRole("link", { name: "video.mp4" }).first().click();
  await expect(page.getByRole("heading", { name: "video.mp4" })).toBeVisible();
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await video.evaluate((v) => { v.muted = true; return v.play(); });
  await expect.poll(() => video.evaluate((v) => v.currentTime), { timeout: 30_000 }).toBeGreaterThan(1);
  await page.screenshot({ path: `${OUT}/detail.png`, fullPage: true });
});

test("OPERATOR는 품질 검토 큐를 본다", async ({ page }) => {
  await signUpAndLogIn(page, "OPERATOR");
  await page.goto("/quality/review");
  await expect(page.getByRole("table", { name: "검토 항목" }).or(page.getByText(/검토할 항목이 없|없습니다/))).toBeVisible();
  await page.screenshot({ path: `${OUT}/quality.png`, fullPage: true });
});
