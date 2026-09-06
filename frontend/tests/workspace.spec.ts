import { test, expect } from "@playwright/test";
test("user analysis, evidence abstention, history and role navigation", async ({
  page,
}) => {
  const analysis = {
    analysisId: 1,
    riskLevel: "SAFE",
    riskScore: 0,
    inputPreview: "의심 문자",
    createdAt: "2026-09-06T12:00:00",
    ruleReason: "탐지 없음",
    recommendedAction: "공식 채널에서 확인하세요.",
    detectedKeywordRespons: [],
    modelResult: {
      status: "COMPLETED",
      decision: "ABSTAIN",
      modelVersion: "test",
    },
  };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = null;
    if (path.endsWith("/login"))
      data = {
        accessToken: "test",
        refreshToken: "test-refresh",
        user: {
          userId: 1,
          name: "혜원",
          email: "test@example.test",
          role: "USER",
        },
      };
    else if (path === "/api/analysis")
      data = route.request().method() === "POST" ? analysis : [analysis];
    else if (path === "/api/chat/sessions")
      data =
        route.request().method() === "POST"
          ? { sessionId: 1, title: "새 질문" }
          : [{ sessionId: 1, title: "새 질문" }];
    else if (path.endsWith("/messages"))
      data = [
        {
          messageId: 1,
          sender: "AI",
          message: "답변에 필요한 공식 문서 근거가 부족합니다.",
          generationStatus: "INSUFFICIENT_EVIDENCE",
          referencedChunks: [],
        },
      ];
    await route.fulfill({ json: { data } });
  });
  await page.goto("/");
  await page.getByLabel("이메일").fill("test@example.test");
  await page.getByLabel("비밀번호").fill("password123");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "혜원 님, 무엇을 확인할까요?" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "서비스 관리" })).toHaveCount(0);
  await page.screenshot({
    path: test.info().outputPath("home.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "의심 문자 분석", exact: true }).click();
  await page.getByLabel("문자 내용").fill("의심 문자 테스트");
  await page.getByRole("button", { name: "분석하기", exact: true }).click();
  await expect(
    page.getByText("판단 보류 · AI가 확실하게 분류하지 못했습니다."),
  ).toBeVisible();
  await expect(
    page.locator(".badge").filter({ hasText: "탐지 없음" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "내 분석 이력", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "의심 문자", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "문서 기반 Q&A" }).click();
  await page.getByRole("button", { name: "+ 새 대화" }).click();
  await expect(
    page.getByText("답변에 필요한 공식 문서 근거가 부족합니다."),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(
    page.getByRole("heading", { name: "다시 만나 반가워요" }),
  ).toBeVisible();
});
test("admin document form and category management", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith("/login")
      ? {
          accessToken: "test",
          refreshToken: "refresh",
          user: { userId: 1, name: "관리자", role: "ADMIN" },
        }
      : path.endsWith("/dashboard")
        ? {
            totalAnalysisCount: 12,
            todayAnalysisCount: 2,
            highRiskCount: 3,
            documentCount: 0,
            keywordCount: 0,
          }
        : [];
    await route.fulfill({ json: { data } });
  });
  await page.goto("/");
  await page.getByLabel("이메일").fill("admin@example.test");
  await page.getByLabel("비밀번호").fill("password123");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("link", { name: "서비스 관리" }).click();
  await expect(page.getByText("전체 분석", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "공식 문서", exact: true }).click();
  await expect(page.getByLabel("PDF 파일 · 최대 10MB")).toBeVisible();
  await page.getByRole("button", { name: "위험 키워드", exact: true }).click();
  await expect(page.getByLabel("카테고리")).toHaveValue("기관사칭");
});
