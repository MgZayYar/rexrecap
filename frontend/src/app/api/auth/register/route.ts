import { NextResponse } from "next/server";

import { backendFetchWithAuth, proxyJson, setAuthCookie } from "@/lib/server-backend";

export async function POST(request: Request) {
  const credentials = await request.json();
  const registration = await backendFetchWithAuth("/auth/register", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  if (!registration.ok) return proxyJson(registration);

  const login = await backendFetchWithAuth("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  if (!login.ok) return proxyJson(login);

  const { access_token: accessToken } = (await login.json()) as { access_token: string };
  const nextResponse = NextResponse.json({ ok: true }, { status: 201 });
  setAuthCookie(nextResponse, accessToken);
  return nextResponse;
}
