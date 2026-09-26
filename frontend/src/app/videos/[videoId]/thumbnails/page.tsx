import { redirect } from "next/navigation";

import { ThumbnailsPanel } from "@/components/thumbnails-panel";
import { getServerSession } from "@/lib/server-auth";

export default async function ThumbnailsPage({ params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getServerSession())) redirect("/login");
  const { videoId } = await params;
  const numericVideoId = Number(videoId);
  if (!Number.isInteger(numericVideoId) || numericVideoId <= 0) redirect("/dashboard");

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl p-6">
      <div className="mb-8">
        <a className="text-sm font-medium text-slate-600 underline" href="/dashboard">
          Back to dashboard
        </a>
        <h1 className="mt-3 text-3xl font-semibold">Thumbnails</h1>
        <p className="mt-2 text-slate-600">
          RexCrop pulls frames from across the video and scores them by sharpness and face
          presence — pick the one that will sell the recap.
        </p>
      </div>
      <ThumbnailsPanel videoId={numericVideoId} />
    </main>
  );
}
