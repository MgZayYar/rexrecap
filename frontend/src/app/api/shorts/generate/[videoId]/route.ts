import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(request: Request, { params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { videoId } = await params;
  return proxyJson(
    await backendFetchWithAuth(`/shorts/generate/${videoId}`, {
      method: "POST",
      body: await request.text(),
    }),
  );
}
