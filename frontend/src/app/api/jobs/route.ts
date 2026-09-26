import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(request: Request) {
  if (!(await getAuthToken())) return unauthorized();

  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") {
    return NextResponse.json({ detail: "Invalid job request" }, { status: 400 });
  }

  const response = await backendFetchWithAuth("/jobs/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return proxyJson(response, 201);
}
