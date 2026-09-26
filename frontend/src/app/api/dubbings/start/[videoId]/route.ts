import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { videoId } = await params;
  const id = Number(videoId);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ detail: "Invalid video id" }, { status: 400 });
  }
  const payload = await request.json().catch(() => ({}));
  const response = await backendFetchWithAuth(`/dubbings/start/${id}`, {
    method: "POST",
    body: JSON.stringify(payload && typeof payload === "object" ? payload : {}),
  });
  return proxyJson(response, 201);
}
