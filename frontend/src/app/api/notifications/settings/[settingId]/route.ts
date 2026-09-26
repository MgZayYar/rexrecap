import { NextRequest, NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

type Params = { params: Promise<{ settingId: string }> };

export async function PATCH(request: NextRequest, { params }: Params) {
  if (!(await getAuthToken())) return unauthorized();
  const { settingId } = await params;
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") {
    return NextResponse.json({ detail: "Invalid notification setting" }, { status: 400 });
  }
  return proxyJson(
    await backendFetchWithAuth(`/notifications/settings/${settingId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    })
  );
}

export async function DELETE(_request: NextRequest, { params }: Params) {
  if (!(await getAuthToken())) return unauthorized();
  const { settingId } = await params;
  const response = await backendFetchWithAuth(`/notifications/settings/${settingId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    return proxyJson(response);
  }
  return new NextResponse(null, { status: 204 });
}
