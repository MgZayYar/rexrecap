import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { backendFetch, readError } from "@/lib/backend";

export async function POST(request: Request) {
  const credentials = await request.json();
  const response = await backendFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  }

  const { access_token: accessToken } = await response.json();
  const nextResponse = NextResponse.json({ ok: true });
  nextResponse.cookies.set(AUTH_COOKIE, accessToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  return nextResponse;
}
