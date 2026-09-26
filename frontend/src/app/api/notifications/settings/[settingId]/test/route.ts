import { NextRequest } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(_request: NextRequest, { params }: { params: Promise<{ settingId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { settingId } = await params;
  return proxyJson(
    await backendFetchWithAuth(`/notifications/settings/${settingId}/test`, { method: "POST" })
  );
}
