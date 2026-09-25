"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ProcessingJob } from "@/lib/job";

const actions: Array<{ jobType: ProcessingJob["job_type"]; label: string }> = [
  { jobType: "transcription", label: "Transcribe" },
  { jobType: "dubbing", label: "Dub" },
  { jobType: "autocrop", label: "Auto-crop" },
  { jobType: "render", label: "Render" },
];

export function VideoJobActions({ videoId }: { videoId: number }) {
  const [starting, setStarting] = useState<ProcessingJob["job_type"] | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function start(jobType: ProcessingJob["job_type"]) {
    setStarting(jobType);
    setMessage(null);
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: videoId, job_type: jobType }),
    });
    setStarting(null);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setMessage(body?.detail ?? "Unable to start job.");
      return;
    }
    setMessage(`${actions.find((action) => action.jobType === jobType)?.label} job queued.`);
  }

  return <div className="space-y-2">
    <div className="flex flex-wrap justify-end gap-2">
      {actions.map((action) => <Button key={action.jobType} variant="outline" size="sm" onClick={() => void start(action.jobType)} disabled={starting !== null}>{starting === action.jobType ? "Starting…" : action.label}</Button>)}
    </div>
    {message && <p className="text-right text-xs text-slate-500" role="status">{message}</p>}
  </div>;
}
