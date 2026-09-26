import { backendFetchWithAuth, getAuthToken, unauthorized } from "@/lib/server-backend";

export async function GET(_: Request, { params }: { params: Promise<{ jobId: string }> }) {
  if (!(await getAuthToken())) return unauthorized();

  const { jobId } = await params;
  const id = Number(jobId);
  if (!Number.isInteger(id) || id <= 0) {
    return new Response("Invalid job id", { status: 400 });
  }

  const response = await backendFetchWithAuth(`/jobs/${id}/output`);
  if (!response.ok) {
    return new Response("Output not available", { status: response.status });
  }
  return new Response(response.body, {
    status: 200,
    headers: {
      "content-type": response.headers.get("content-type") ?? "video/mp4",
      "content-disposition":
        response.headers.get("content-disposition") ?? `attachment; filename="rexcrop-output-${id}.mp4"`,
    },
  });
}
