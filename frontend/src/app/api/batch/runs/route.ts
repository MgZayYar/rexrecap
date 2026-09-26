
import type { NextRequest } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET() {
  if (!(await getAuthToken())) return unauthorized();
  return proxyJson(await backendFetchWithAuth("/batch/runs"));
}

export async function POST(request: NextRequest) {
  if (!(await getAuthToken())) return unauthorized();
  const payload = await request.json().catch(() => ({}));
  return proxyJson(
    await backendFetchWithAuth("/batch/runs", {
      method: "POST",
      body: JSON.stringify(payload && typeof payload === "object" ? payload : {}),
    }),
    201
  );
}
