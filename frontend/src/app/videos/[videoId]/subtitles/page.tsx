import { redirect } from "next/navigation";

import { SubtitleEditor } from "@/components/subtitle-editor";
import { getServerSession } from "@/lib/server-auth";

export default async function SubtitleEditorPage({ params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getServerSession())) redirect("/login");
  const { videoId } = await params;
  const numericVideoId = Number(videoId);
  if (!Number.isInteger(numericVideoId) || numericVideoId <= 0) redirect("/dashboard");
  return <main className="mx-auto min-h-screen w-full max-w-7xl p-6"><div className="mb-8"><a className="text-sm font-medium text-slate-600 underline" href={`/videos/${numericVideoId}/transcript`}>Back to transcript</a><h1 className="mt-3 text-3xl font-semibold">Subtitle editor</h1><p className="mt-2 text-slate-600">Refine timing, edit text, and export production-ready captions.</p></div><SubtitleEditor videoId={numericVideoId} /></main>;
}
