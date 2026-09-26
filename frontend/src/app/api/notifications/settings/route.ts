import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET() {
  if (!(await getAuthToken())) return unauthorized();
  return proxyJson(await backendFetchWithAuth("/notifications/settings"));
}

export async function POST(request: Request) {
  if (!(await getAuthToken())) return unauthorized();
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") {
    return NextResponse.json({ detail: "Invalid notification setting" }, { status: 400 });
  }
  return proxyJson(
    await backendFetchWithAuth("/notifications/settings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
    201
  );
}
