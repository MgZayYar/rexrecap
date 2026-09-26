import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(_request: Request, { params }: { params: Promise<{ draftId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { draftId } = await params;
  return proxyJson(await backendFetchWithAuth(`/assistant/recap/${encodeURIComponent(draftId)}`));
}
