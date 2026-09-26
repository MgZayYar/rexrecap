/**
 * Server-only helpers for Next.js route handlers.
 *
 * Centralizes the backend-for-frontend plumbing that every /api route needs:
 * reading the auth cookie, attaching the JWT, and normalizing responses.
 * Browser components must never import this module (it uses next/headers).
 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { API_URL, readError } from "@/lib/backend";

export async function getAuthToken(): Promise<string | null> {
  return (await cookies()).get(AUTH_COOKIE)?.value ?? null;
}

export function unauthorized(): NextResponse {
  return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
}

/** Fetch the FastAPI backend with the current user's JWT attached. */
export async function backendFetchWithAuth(path: string, init?: RequestInit): Promise<Response> {
  const token = await getAuthToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
}

/** Proxy a backend JSON response, normalizing errors to { detail }. */
export async function proxyJson(response: Response, successStatus = 200): Promise<NextResponse> {
  if (!response.ok) {
    return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  }
  return NextResponse.json(await response.json(), { status: successStatus });
}

const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: 60 * 60,
};

export function setAuthCookie(response: NextResponse, token: string): void {
  response.cookies.set(AUTH_COOKIE, token, COOKIE_OPTIONS);
}

export function clearAuthCookie(response: NextResponse): void {
  response.cookies.set(AUTH_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
}
