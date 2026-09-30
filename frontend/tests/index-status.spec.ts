import { test, expect } from "@playwright/test";

test("admin distinguishes missing and stale embeddings per model and clears failed results", async ({
  page,
}) => {
  let fail = false;
  const queries: string[] = [];
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let data: unknown = [];
    if (url.pathname.endsWith("/login"))
      data = {
        accessToken: "test",
        refreshToken: "refresh",
        user: { userId: 1, name: "관리자", role: "ADMIN" },
      };
    else if (url.pathname.endsWith("/dashboard")) data = {};
    else if (url.pathname.endsWith("/documents"))
      data = [
        {
          documentId: 1,
          title: "신고 안내",
          source: "테스트 기관",
          status: "COMPLETED",
          chunkCount: 3,
        },
      ];
    else if (url.pathname.endsWith("/index-status")) {
      expect(route.request().method()).toBe("GET");
      if (fail) {
        await route.fulfill({
          status: 404,
          json: { message: "문서를 찾을 수 없습니다." },
        });
        return;
      }
      const model = url.searchParams.get("model")!;
      queries.push(model);
      data = {
        documentId: 1,
        documentStatus: "COMPLETED",
        embeddingModel: model,
        status: model === "text-embedding-3-small" ? "STALE" : "NOT_INDEXED",
        totalChunks: 3,
        currentChunks: model === "text-embedding-3-small" ? 1 : 0,
        missingChunks: model === "text-embedding-3-small" ? 1 : 3,
        staleChunks: model === "text-embedding-3-small" ? 1 : 0,
      };
    }
    await route.fulfill({ json: { data } });
  });
  await page.goto("/");
  await page.getByLabel("이메일").fill("admin@example.test");
  await page.getByLabel("비밀번호").fill("password123");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("link", { name: "서비스 관리" }).click();
  await page.getByRole("button", { name: "공식 문서", exact: true }).click();
  await page.getByRole("button", { name: "임베딩 상태 확인" }).click();
  const panel = page.getByRole("region", { name: "문서 임베딩 상태" });
  await panel.getByRole("button", { name: "상태 조회", exact: true }).click();
  await expect(
    panel.getByRole("heading", { name: "본문과 임베딩 불일치" }),
  ).toBeVisible();
  await expect(
    panel.getByText("전체 3 · 본문 일치 1 · 누락 1 · 내용 불일치 1"),
  ).toBeVisible();
  await panel
    .getByLabel("임베딩 모델", { exact: true })
    .fill("gemini-embedding-001");
  await expect(
    panel.getByText("본문과 임베딩 불일치", { exact: true }),
  ).toHaveCount(0);
  await panel.getByRole("button", { name: "상태 조회", exact: true }).click();
  await expect(
    panel.getByRole("heading", { name: "미인덱싱", exact: true }),
  ).toBeVisible();
  // React StrictMode can repeat mount effects in the dev server.
  expect([...new Set(queries)]).toEqual([
    "text-embedding-3-small",
    "gemini-embedding-001",
  ]);
  await page.screenshot({
    path: test.info().outputPath("document-index-status.png"),
    fullPage: true,
  });
  fail = true;
  await panel.getByRole("button", { name: "임베딩 상태 새로고침" }).click();
  await expect(panel.getByRole("alert")).toHaveText("문서를 찾을 수 없습니다.");
  await expect(
    panel.getByRole("heading", { name: "미인덱싱", exact: true }),
  ).toHaveCount(0);
});
