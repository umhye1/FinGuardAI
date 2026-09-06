import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, setSession, getSession, json } from "./api";
const s = {
  accessToken: "old",
  refreshToken: "refresh",
  user: {
    userId: 1,
    name: "Test",
    email: "test@example.test",
    role: "USER" as const,
  },
};
const reply = (status: number, data: unknown) =>
  new Response(JSON.stringify({ data }), { status });
beforeEach(() => {
  setSession({ ...s });
  vi.stubGlobal("window", { dispatchEvent: vi.fn() });
});
afterEach(() => vi.unstubAllGlobals());
describe("API session handling", () => {
  it("shares a single refresh for concurrent unauthorized requests", async () => {
    let rotations = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options: RequestInit) => {
        if (url.endsWith("/refresh")) {
          rotations++;
          await new Promise((r) => setTimeout(r, 10));
          return reply(200, { ...s, accessToken: "new" });
        }
        return (options.headers as Headers).get("Authorization") ===
          "Bearer new"
          ? reply(200, "ok")
          : reply(401, null);
      }),
    );
    expect(await Promise.all([api("/one"), api("/two")])).toEqual(["ok", "ok"]);
    expect(rotations).toBe(1);
  });
  it("clears session when refresh is rejected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => reply(401, null)),
    );
    await expect(api("/one")).rejects.toThrow("로그인이 만료");
    expect(getSession()).toBeNull();
  });
  it("does not refresh a rejected login", async () => {
    const fetch = vi.fn(async () => reply(401, null));
    vi.stubGlobal("fetch", fetch);
    await expect(api("/auth/login", json("POST", {}), false)).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("does not replace a newer login with an old refresh result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/refresh")) {
          setSession({ ...s, accessToken: "another-login" });
          return reply(200, { ...s, accessToken: "stale" });
        }
        return reply(401, null);
      }),
    );
    await expect(api("/one")).rejects.toThrow("로그인이 변경");
    expect(getSession()?.accessToken).toBe("another-login");
  });
  it("allows browser to generate the multipart boundary", async () => {
    const fetch = vi.fn(async () => reply(200, null));
    vi.stubGlobal("fetch", fetch);
    const body = new FormData();
    body.set("title", "document");
    await api("/admin/documents", { method: "POST", body });
    expect(
      (fetch.mock.calls[0] as unknown as [string, RequestInit])[1].headers,
    ).toBeInstanceOf(Headers);
    expect(
      (
        (fetch.mock.calls[0] as unknown as [string, RequestInit])[1]
          .headers as Headers
      ).has("Content-Type"),
    ).toBe(false);
  });
});
