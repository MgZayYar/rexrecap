import { NextRequest } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ batchId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { batchId } = await params;
  return proxyJson(await backendFetchWithAuth(`/batch/runs/${encodeURIComponent(batchId)}`));
}
