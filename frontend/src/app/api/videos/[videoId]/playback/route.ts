import { NextResponse } from "next/server";

import { readError } from "@/lib/backend";
import { backendFetchWithAuth, getAuthToken, unauthorized } from "@/lib/server-backend";

export async function GET(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const { videoId } = await params;
  const range = request.headers.get("range");
  const response = await backendFetchWithAuth(`/videos/${encodeURIComponent(videoId)}/playback`, {
    headers: range ? { Range: range } : undefined,
  });
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });

  const headers = new Headers();
  for (const name of ["accept-ranges", "content-length", "content-range", "content-type"]) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new NextResponse(response.body, { status: response.status, headers });
}
