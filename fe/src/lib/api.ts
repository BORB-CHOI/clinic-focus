// BE API fetch 래퍼 — 단일 진입점 (axios 안 씀, fetch 사용)
//
// - base URL 은 env.API_BASE_URL (dev: http://localhost:8000, prod: CloudFront).
// - BE 응답 규약: 성공 {data, meta?} / 에러 {error:{code,message}} → 에러는 ApiError 로 throw.
// - 쿼리 파라미터는 빈 값/null/undefined 자동 제외.

import { API_BASE_URL } from "./env";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue>;

function buildUrl(path: string, params?: QueryParams): string {
  const base = API_BASE_URL || "";
  // base 가 절대 URL(http://...)이면 origin 무시되고 그게 쓰임; 빈 값이면 상대경로(프록시).
  const url = new URL(`${base}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== null && v !== undefined && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }
  return url.toString();
}

async function request<T>(path: string, init?: RequestInit, params?: QueryParams): Promise<T> {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (e) {
    throw new ApiError("NETWORK_ERROR", "서버에 연결하지 못했습니다", 0);
  }
  const json = (await res.json().catch(() => null)) as
    | { data?: unknown; meta?: unknown; error?: { code: string; message: string } }
    | null;

  if (!res.ok || (json && json.error)) {
    const err = json?.error;
    throw new ApiError(
      err?.code ?? `HTTP_${res.status}`,
      err?.message ?? res.statusText ?? "요청에 실패했습니다",
      res.status,
    );
  }
  return json as T;
}

/** GET — {data, meta} 봉투 전체를 그대로 돌려준다 (호출부가 data/meta 분해). */
export function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  return request<T>(path, { method: "GET" }, params);
}

/** POST — body 를 JSON 으로 전송. */
export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}
