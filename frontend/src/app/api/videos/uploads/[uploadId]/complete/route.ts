import { backendFetchWithAuth, getAuthToken, proxyJson, unauthorized } from "@/lib/server-backend";

export async function POST(_request: Request, { params }: { params: Promise<{ uploadId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();
  const { uploadId } = await params;
  return proxyJson(
    await backendFetchWithAuth(`/videos/uploads/${uploadId}/complete`, { method: "POST" }),
    201,
  );
}
