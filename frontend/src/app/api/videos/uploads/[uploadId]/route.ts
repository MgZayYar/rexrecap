import { NextResponse } from "next/server";

import { readError } from "@/lib/backend";
import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

type Params = { params: Promise<{ uploadId: string }> };

export async function GET(_request: Request, { params }: Params) {
  if (!(await getAuthToken())) return unauthorized();
  const { uploadId } = await params;
  return proxyJson(await backendFetchWithAuth(`/videos/uploads/${uploadId}`));
}

export async function PATCH(request: Request, { params }: Params) {
  if (!(await getAuthToken())) return unauthorized();
  const { uploadId } = await params;
  const offset = request.headers.get("upload-offset");
  if (!offset) return NextResponse.json({ detail: "Upload-Offset header is required" }, { status: 400 });
  const chunk = await request.arrayBuffer();
  if (chunk.byteLength === 0) {
    return NextResponse.json({ detail: "Empty chunk" }, { status: 400 });
  }
  return proxyJson(
    await backendFetchWithAuth(`/videos/uploads/${uploadId}`, {
      method: "PATCH",
      headers: { "Upload-Offset": offset, "Content-Type": "application/octet-stream" },
      body: chunk,
    }),
  );
}

export async function DELETE(_request: Request, { params }: Params) {
  if (!(await getAuthToken())) return unauthorized();
  const { uploadId } = await params;
  const response = await backendFetchWithAuth(`/videos/uploads/${uploadId}`, { method: "DELETE" });
  if (!response.ok) {
    return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  }
  return new NextResponse(null, { status: 204 });
}
