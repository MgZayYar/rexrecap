import { NextRequest } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(_request: NextRequest, { params }: { params: Promise<{ thumbnailId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { thumbnailId } = await params;
  return proxyJson(
    await backendFetchWithAuth(`/thumbnails/${encodeURIComponent(thumbnailId)}/select`, { method: "POST" })
  );
}
