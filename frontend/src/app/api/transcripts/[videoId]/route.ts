import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(_: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const { videoId } = await params;
  return proxyJson(await backendFetchWithAuth(`/transcripts/${encodeURIComponent(videoId)}`));
}

export async function POST(_: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const { videoId } = await params;
  const response = await backendFetchWithAuth(`/transcripts/start/${encodeURIComponent(videoId)}`, {
    method: "POST",
  });
  return proxyJson(response, 201);
}
