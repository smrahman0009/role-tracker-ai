/**
 * Typed fetch wrapper for the Role Tracker API.
 *
 * Responsibilities:
 *  - Inject `Authorization: Bearer <token>` from auth storage on every
 *    request (skipped when the token is empty — backend's bearer
 *    middleware also skips when APP_TOKEN env var is unset).
 *  - Prefix `/api/*` so Vite's dev-server proxy forwards to the
 *    FastAPI backend on port 8000 (production deploys serve both
 *    from the same origin, no proxy needed).
 *  - Surface errors as a typed `ApiClientError` with status + detail
 *    so consumers can branch (401 → bounce to /login, 422 → show
 *    inline validation, etc.).
 *  - Return parsed JSON for normal responses, raw `Response` for
 *    file downloads.
 */

import { getAuth } from "@/lib/auth";

export class ApiClientError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

interface RequestOptions {
  /** HTTP method. Default GET. */
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  /** JSON body to send. Auto-serialised + content-type header set. */
  json?: unknown;
  /** FormData body (overrides json). For file upload. */
  formData?: FormData;
  /** Query params. Values joined with "&"; arrays become CSVs. */
  query?: Record<string, string | number | boolean | string[] | undefined>;
  /** Pass `false` to skip auth header even if token is set. Rare. */
  withAuth?: boolean;
}

function buildUrl(
  path: string,
  query?: RequestOptions["query"],
): string {
  // Vite dev proxy strips /api/* prefix and forwards to backend.
  // In production we serve the SPA from the same origin as the API,
  // so the relative URL works there too.
  const url = new URL(`/api${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null) continue;
      if (Array.isArray(value)) {
        if (value.length > 0) url.searchParams.set(key, value.join(","));
      } else {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.pathname + url.search;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", json, formData, query, withAuth = true } = options;

  const headers: Record<string, string> = {};
  if (json !== undefined) headers["Content-Type"] = "application/json";

  if (withAuth) {
    const { appToken } = getAuth();
    if (appToken) headers["Authorization"] = `Bearer ${appToken}`;
  }

  const init: RequestInit = { method, headers };
  if (formData) init.body = formData;
  else if (json !== undefined) init.body = JSON.stringify(json);

  const response = await fetch(buildUrl(path, query), init);

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      // FastAPI returns {detail: "..."} or {detail: [...]} — both stringifiable.
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (body.detail !== undefined) {
        detail = JSON.stringify(body.detail);
      }
    } catch {
      // Body wasn't JSON; keep the status-line default.
    }
    throw new ApiClientError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * For endpoints that return non-JSON (PDF, Markdown download). Caller
 * gets the raw Response and decides how to handle it.
 */
async function requestRaw(
  path: string,
  options: RequestOptions = {},
): Promise<Response> {
  const { method = "GET", query, withAuth = true } = options;
  const headers: Record<string, string> = {};
  if (withAuth) {
    const { appToken } = getAuth();
    if (appToken) headers["Authorization"] = `Bearer ${appToken}`;
  }
  const response = await fetch(buildUrl(path, query), { method, headers });
  if (!response.ok) {
    throw new ApiClientError(response.status, `HTTP ${response.status}`);
  }
  return response;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "GET", query }),
  post: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "POST", json }),
  put: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "PUT", json }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", formData }),
  raw: requestRaw,
};
