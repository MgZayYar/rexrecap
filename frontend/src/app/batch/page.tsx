import { redirect } from "next/navigation";

import { BatchPanel } from "@/components/batch-panel";
import { getServerSession } from "@/lib/server-auth";

export default async function BatchPage() {
  if (!(await getServerSession())) redirect("/login");

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl p-6">
      <div className="mb-8">
        <a className="text-sm font-medium text-slate-600 underline" href="/dashboard">
          Back to dashboard
        </a>
        <h1 className="mt-3 text-3xl font-semibold">Batch processing</h1>
        <p className="mt-2 text-slate-600">
          Run the same workflow across a whole set of videos in one go — transcribe the
          week&apos;s uploads, then dub them all once the transcripts land.
        </p>
      </div>
      <BatchPanel />
    </main>
  );
}
