/**
 * Typed API client for browser components.
 *
 * All client-side calls to the Next.js /api routes go through here so error
 * handling and request configuration stay in one place. Server code (route
 * handlers) uses lib/server-backend instead.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function readErrorDetail(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  const detail = (body as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" && detail.length > 0
    ? detail
    : "Something went wrong. Please try again.";
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) throw new ApiError(response.status, await readErrorDetail(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** GET/POST/etc. against a Next.js /api route with normalized errors. */
export function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  return fetch(path, { ...init, cache: "no-store" }).then(parseJson<T>);
}

export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return apiFetch<T>(path, init);
}

export function apiPost<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const payload = body === undefined ? undefined : JSON.stringify(body);
  if (payload !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return apiFetch<T>(path, { ...init, method: "POST", headers, body: payload });
}

/** Extract a user-facing message from an unknown caught error. */
export function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.detail : fallback;
}
