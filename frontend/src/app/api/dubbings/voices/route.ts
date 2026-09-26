import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function GET(request: Request) {
  if (!(await getAuthToken())) return unauthorized();
  const { searchParams } = new URL(request.url);
  const query = new URLSearchParams();
  const provider = searchParams.get("provider");
  const language = searchParams.get("language");
  if (provider) query.set("provider", provider);
  if (language) query.set("language", language);
  const suffix = query.toString() ? `?${query}` : "";
  return proxyJson(await backendFetchWithAuth(`/dubbings/voices${suffix}`));
}
