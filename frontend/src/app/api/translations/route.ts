import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { backendFetch, readError } from "@/lib/backend";

export async function POST(request: Request) {
  const token = (await cookies()).get(AUTH_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") return NextResponse.json({ detail: "Invalid translation request" }, { status: 400 });
  const response = await backendFetch("/translations", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  return NextResponse.json(await response.json(), { status: response.status });
}
