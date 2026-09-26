import { redirect } from "next/navigation";

import { DubbingPanel } from "@/components/dubbing-panel";
import { getServerSession } from "@/lib/server-auth";

export default async function DubbingPage({ params }: { params: Promise<{ videoId: string }> }) {
  if (!(await getServerSession())) redirect("/login");
  const { videoId } = await params;
  const numericVideoId = Number(videoId);
  if (!Number.isInteger(numericVideoId) || numericVideoId <= 0) redirect("/dashboard");

  return <main className="mx-auto min-h-screen w-full max-w-4xl p-6"><div className="mb-8"><a className="text-sm font-medium text-slate-600 underline" href="/dashboard">Back to dashboard</a><h1 className="mt-3 text-3xl font-semibold">AI Voice Dubbing</h1><p className="mt-2 text-slate-600">Pick a voice, preview it, then dub the whole video. Speaker turns are detected from pauses; the original audio stays as a quiet bed.</p></div><DubbingPanel videoId={numericVideoId} /></main>;
}
