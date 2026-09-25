import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";
import { API_URL, readError } from "@/lib/backend";

export async function POST(request: Request) {
  const token = (await cookies()).get(AUTH_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File)) return NextResponse.json({ detail: "A video file is required" }, { status: 400 });

  const outbound = new FormData();
  outbound.append("file", file);
  const response = await fetch(`${API_URL}/videos/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: outbound,
    cache: "no-store",
  });
  if (!response.ok) return NextResponse.json({ detail: await readError(response) }, { status: response.status });
  return NextResponse.json(await response.json(), { status: 201 });
}
