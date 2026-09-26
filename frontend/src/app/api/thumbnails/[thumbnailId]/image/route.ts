import { NextRequest, NextResponse } from "next/server";

import { readError } from "@/lib/backend";
import { backendFetchWithAuth, getAuthToken, unauthorized } from "@/lib/server-backend";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ thumbnailId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { thumbnailId } = await params;
  const response = await backendFetchWithAuth(`/thumbnails/${encodeURIComponent(thumbnailId)}/image`);
  if (!response.ok) {
    return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  }
  return new NextResponse(response.body, {
    headers: { "Content-Type": "image/jpeg", "Cache-Control": "private, max-age=3600" },
  });
}
