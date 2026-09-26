import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET() {
  if (!(await getAuthToken())) return unauthorized();
  return proxyJson(await backendFetchWithAuth("/jobs/workers"));
}
