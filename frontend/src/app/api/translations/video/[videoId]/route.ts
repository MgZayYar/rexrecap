import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { backendFetch, readError } from "@/lib/backend";

export async function GET(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  const token = (await cookies()).get(AUTH_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  const targetLanguage = new URL(request.url).searchParams.get("target_language");
  if (!targetLanguage) return NextResponse.json({ detail: "target_language is required" }, { status: 400 });
  const { videoId } = await params;
  const response = await backendFetch(`/translations/video/${encodeURIComponent(videoId)}?target_language=${encodeURIComponent(targetLanguage)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  return NextResponse.json(await response.json());
}
