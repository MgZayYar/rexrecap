import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { videoId } = await params;

  const payload = await request.json().catch(() => null);
  const response = await backendFetchWithAuth(`/subtitles/burn/${encodeURIComponent(videoId)}`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
  return proxyJson(response, 201);
}
