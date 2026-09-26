import { NextRequest } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(_request: NextRequest, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { videoId } = await params;
  return proxyJson(
    await backendFetchWithAuth(`/assistant/recap/${encodeURIComponent(videoId)}`, { method: "POST" }),
    201
  );
}
