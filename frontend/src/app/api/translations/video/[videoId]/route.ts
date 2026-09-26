import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const targetLanguage = new URL(request.url).searchParams.get("target_language");
  if (!targetLanguage) return NextResponse.json({ detail: "target_language is required" }, { status: 400 });

  const { videoId } = await params;
  const path = `/translations/video/${encodeURIComponent(videoId)}?target_language=${encodeURIComponent(targetLanguage)}`;
  return proxyJson(await backendFetchWithAuth(path));
}
