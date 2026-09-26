import { NextResponse } from "next/server";

import { backendFetchWithAuth, proxyJson, setAuthCookie } from "@/lib/server-backend";

export async function POST(request: Request) {
  const credentials = await request.json();
  const response = await backendFetchWithAuth("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  if (!response.ok) return proxyJson(response);

  const { access_token: accessToken } = (await response.json()) as { access_token: string };
  const nextResponse = NextResponse.json({ ok: true });
  setAuthCookie(nextResponse, accessToken);
  return nextResponse;
}
