import { NextResponse } from "next/server";

import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(request: Request) {
  if (!(await getAuthToken())) return unauthorized();

  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File)) return NextResponse.json({ detail: "A video file is required" }, { status: 400 });

  const outbound = new FormData();
  outbound.append("file", file);
  const response = await backendFetchWithAuth("/videos/upload", { method: "POST", body: outbound });
  return proxyJson(response, 201);
}
