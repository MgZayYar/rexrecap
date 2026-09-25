import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { API_URL, readError } from "@/lib/backend";

export async function GET(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  const token = (await cookies()).get(AUTH_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { videoId } = await params;
  const range = request.headers.get("range");
  const response = await fetch(`${API_URL}/videos/${encodeURIComponent(videoId)}/playback`, {
    headers: { Authorization: `Bearer ${token}`, ...(range ? { Range: range } : {}) },
    cache: "no-store",
  });
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });

  const headers = new Headers();
  for (const name of ["accept-ranges", "content-length", "content-range", "content-type"]) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new NextResponse(response.body, { status: response.status, headers });
}
