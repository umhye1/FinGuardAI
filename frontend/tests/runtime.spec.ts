import { test, expect } from "@playwright/test";

// Opt-in real backend/AI test, no route mocks. Only use an isolated fixture DB.
test("real services preserve clarification, missing-evidence and conflict decisions", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.FG_RUNTIME_E2E !== "1",
    "Requires isolated runtime fixture and actual servers",
  );
  const email = `runtime-${Date.now()}-${test.info().project.name}@example.test`;
  const password = "RuntimeTest123!";
  const signup = await request.post("/api/auth/signup", {
    data: { email, password, name: "검증" },
  });
  expect(signup.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill(password);
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("link", { name: "문서 기반 Q&A" }).click();
  await page.getByRole("button", { name: "+ 새 대화" }).click();
  for (const [question, badge, reason] of [
    ["어떻게 해야 하나요?", "추가 정보 필요", "NEEDS_CLARIFICATION"],
    ["휴대폰 소액결제 피해", "근거 부족", "MISSING_REQUIRED_DOCUMENT"],
    ["계좌 송금 피해", "근거 충돌 · 답변 보류", "CONFLICTING_EVIDENCE"],
  ]) {
    await page.getByLabel("질문", { exact: true }).fill(question);
    const response = page.waitForResponse(
      (r) => r.url().endsWith("/messages") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "질문 보내기" }).click();
    const r = await response;
    expect(r.ok()).toBeTruthy();
    expect(JSON.stringify(await r.json())).toContain(reason);
    await expect(page.getByText(badge, { exact: true })).toBeVisible();
  }
  await page.reload();
  // Tokens are intentionally memory-only: log in again to verify persisted history.
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill(password);
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("link", { name: "문서 기반 Q&A" }).click();
  await page.locator("button.session").first().click();
  await expect(
    page.getByText("근거 충돌 · 답변 보류", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "공식 출처 확인" })).toHaveCount(
    0,
  );
  await page.screenshot({
    path: test.info().outputPath("runtime-decisions.png"),
    fullPage: true,
  });
});
