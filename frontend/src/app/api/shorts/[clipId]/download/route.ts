import { backendFetchWithAuth, getAuthToken, unauthorized } from "@/lib/server-backend";

export async function GET(_: Request, { params }: { params: Promise<{ clipId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const { clipId } = await params;
  const id = Number(clipId);
  if (!Number.isInteger(id) || id <= 0) {
    return new Response("Invalid clip id", { status: 400 });
  }

  const response = await backendFetchWithAuth(`/shorts/${id}/download`);
  if (!response.ok) {
    return new Response("Clip not available", { status: response.status });
  }
  return new Response(response.body, {
    status: 200,
    headers: {
      "content-type": response.headers.get("content-type") ?? "video/mp4",
      "content-disposition":
        response.headers.get("content-disposition") ?? `attachment; filename="rexcrop-short-${id}.mp4"`,
    },
  });
}
