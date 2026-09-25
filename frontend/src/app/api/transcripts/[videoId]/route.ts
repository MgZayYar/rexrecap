import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { backendFetch, readError } from "@/lib/backend";

async function getToken() {
  return (await cookies()).get(AUTH_COOKIE)?.value;
}

export async function GET(_: Request, { params }: { params: Promise<{ videoId: string }> }) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  const { videoId } = await params;
  const response = await backendFetch(`/transcripts/${encodeURIComponent(videoId)}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  return NextResponse.json(await response.json());
}

export async function POST(_: Request, { params }: { params: Promise<{ videoId: string }> }) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  const { videoId } = await params;
  const response = await backendFetch(`/transcripts/start/${encodeURIComponent(videoId)}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  return NextResponse.json(await response.json(), { status: 201 });
}
