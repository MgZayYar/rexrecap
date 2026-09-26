import { NextRequest } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(request: NextRequest, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { videoId } = await params;
  const payload = await request.json().catch(() => ({}));
  return proxyJson(
    await backendFetchWithAuth(`/thumbnails/generate/${encodeURIComponent(videoId)}`, {
      method: "POST",
      body: JSON.stringify(payload && typeof payload === "object" ? payload : {}),
    }),
    201
  );
}
