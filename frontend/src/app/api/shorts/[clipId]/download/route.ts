import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, unauthorized } from "@/lib/server-backend";

export async function GET(_: Request, { params }: { params: Promise<{ clipId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const { clipId } = await params;
  const id = Number(clipId);
  if (!Number.isInteger(id) || id <= 0) {
    return new Response("Invalid clip id", { status: 400 });
  }

  // redirect: "manual" so a presigned object-storage URL is passed to the
  // browser instead of being proxied through the Next.js server.
  const response = await backendFetchWithAuth(`/shorts/${id}/download`, { redirect: "manual" });
  if (response.status === 302 || response.status === 307) {
    const location = response.headers.get("location");
    if (location) return NextResponse.redirect(location);
  }
  if (!response.ok) {
    return new Response("Clip not available", { status: response.status });
  }
  return new Response(response.body, {
    status: 200,
    headers: {
      "content-type": response.headers.get("content-type") ?? "video/mp4",
      "content-disposition":
        response.headers.get("content-disposition") ?? `attachment; filename="rexcrop-short-${id}.mp4"`,
    },
  });
}
