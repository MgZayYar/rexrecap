import { backendFetchWithAuth, getAuthToken, unauthorized } from "@/lib/server-backend";

export async function POST(request: Request) {
  if (!(await getAuthToken())) return unauthorized();
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload.text !== "string" || typeof payload.voice !== "string") {
    return new Response("Invalid preview request", { status: 400 });
  }
  const response = await backendFetchWithAuth("/dubbings/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!response.ok) return new Response("Preview unavailable", { status: response.status });
  return new Response(response.body, {
    status: 200,
    headers: { "content-type": response.headers.get("content-type") ?? "audio/mpeg" },
  });
}
