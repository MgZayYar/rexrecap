import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(_request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { videoId } = await params;
  return proxyJson(await backendFetchWithAuth(`/assistant/recap/video/${encodeURIComponent(videoId)}`));
}
