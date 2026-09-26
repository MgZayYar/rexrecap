import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET() {
  if (!(await getAuthToken())) return unauthorized();
  return proxyJson(await backendFetchWithAuth("/projects"));
}

export async function POST(request: Request) {
  if (!(await getAuthToken())) return unauthorized();

  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object" || typeof payload.name !== "string" || payload.name.trim() === "") {
    return NextResponse.json({ detail: "A project name is required" }, { status: 400 });
  }

  const response = await backendFetchWithAuth("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return proxyJson(response, 201);
}
