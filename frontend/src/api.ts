import type { Session } from "./types";
// Tokens intentionally live only in memory. Reloading requires a new login.
let session: Session | null = null;
let refresh: Promise<void> | null = null;
let generation = 0;
export function setSession(value: Session | null) {
  session = value;
  generation++;
}
export function getSession() {
  return session;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
async function send(path: string, init: RequestInit, token?: string) {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  try {
    return await fetch("/api" + path, {
      ...init,
      headers,
      signal: init.signal ?? AbortSignal.timeout(30000),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(
      "서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      0,
    );
  }
}
export async function api<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const current = generation;
  let response = await send(
    path,
    init,
    authenticated ? session?.accessToken : undefined,
  );
  if (
    response.status === 401 &&
    authenticated &&
    session &&
    current === generation
  ) {
    if (!refresh) {
      const token = session.refreshToken;
      refresh = (async () => {
        const r = await send("/auth/refresh", {
          method: "POST",
          body: JSON.stringify({ refreshToken: token }),
        });
        if (!r.ok)
          throw new ApiError(
            "로그인이 만료되었습니다. 다시 로그인해 주세요.",
            401,
          );
        const result = await r.json();
        if (current === generation) session = result.data;
      })()
        .catch((e) => {
          if (current === generation) {
            setSession(null);
            window.dispatchEvent(new Event("session-expired"));
          }
          throw e;
        })
        .finally(() => {
          refresh = null;
        });
    }
    await refresh;
    if (current !== generation)
      throw new ApiError("로그인이 변경되었습니다.", 401);
    response = await send(path, init, session?.accessToken);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      body?.message || `요청을 처리하지 못했습니다. (${response.status})`,
      response.status,
    );
  return body?.data as T;
}
export const json = (method: string, data: unknown): RequestInit => ({
  method,
  body: JSON.stringify(data),
});
