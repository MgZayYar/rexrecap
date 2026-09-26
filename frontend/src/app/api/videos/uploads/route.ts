import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(request: Request) {
  if (!(await getAuthToken())) return unauthorized();
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") {
    return NextResponse.json({ detail: "filename, content_type, and total_bytes are required" }, { status: 400 });
  }
  return proxyJson(
    await backendFetchWithAuth("/videos/uploads", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
    201,
  );
}
