import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function PATCH(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { videoId } = await params;
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") {
    return NextResponse.json({ detail: "Invalid video update" }, { status: 400 });
  }
  return proxyJson(await backendFetchWithAuth(`/videos/${videoId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }));
}
