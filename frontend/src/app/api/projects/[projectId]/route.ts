import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(_request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { projectId } = await params;
  return proxyJson(await backendFetchWithAuth(`/projects/${projectId}`));
}

export async function PATCH(request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { projectId } = await params;
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") {
    return NextResponse.json({ detail: "Invalid project update" }, { status: 400 });
  }
  return proxyJson(await backendFetchWithAuth(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }));
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { projectId } = await params;
  const response = await backendFetchWithAuth(`/projects/${projectId}`, { method: "DELETE" });
  if (!response.ok) return proxyJson(response);
  return new NextResponse(null, { status: 204 });
}
