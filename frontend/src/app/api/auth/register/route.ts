import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { backendFetch, readError } from "@/lib/backend";

export async function POST(request: Request) {
  const credentials = await request.json();
  const registration = await backendFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(credentials),
  });

  if (!registration.ok) {
    return NextResponse.json({ detail: await readError(registration) }, { status: registration.status });
  }

  const login = await backendFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  if (!login.ok) {
    return NextResponse.json({ detail: await readError(login) }, { status: login.status });
  }

  const { access_token: accessToken } = await login.json();
  const nextResponse = NextResponse.json({ ok: true }, { status: 201 });
  nextResponse.cookies.set(AUTH_COOKIE, accessToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  return nextResponse;
}
