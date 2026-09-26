import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(_request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { jobId } = await params;
  return proxyJson(await backendFetchWithAuth(`/jobs/${jobId}/cancel`, { method: "POST" }));
}
