import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(_request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { projectId } = await params;
  return proxyJson(await backendFetchWithAuth(`/projects/${projectId}/videos`));
}
