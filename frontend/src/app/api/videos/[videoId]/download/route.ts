import { NextResponse } from "next/server";

import { readError } from "@/lib/backend";
import { backendFetchWithAuth, getAuthToken, unauthorized } from "@/lib/server-backend";

export async function GET(_: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const { videoId } = await params;
  const response = await backendFetchWithAuth(`/videos/${encodeURIComponent(videoId)}/download`);
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });

  return new NextResponse(response.body, {
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/octet-stream",
      "Content-Disposition": response.headers.get("Content-Disposition") ?? "attachment",
    },
  });
}
