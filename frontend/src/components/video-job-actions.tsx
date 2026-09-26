"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { apiPost, toMessage } from "@/lib/api-client";
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
    try {
      await apiPost("/api/jobs", { video_id: videoId, job_type: jobType });
      setMessage(`${actions.find((action) => action.jobType === jobType)?.label} job queued.`);
    } catch (err) {
      setMessage(toMessage(err, "Unable to start job."));
    } finally {
      setStarting(null);
    }
  }

  return <div className="space-y-2">
    <div className="flex flex-wrap justify-end gap-2">
      {actions.map((action) => <Button key={action.jobType} variant="outline" size="sm" onClick={() => void start(action.jobType)} disabled={starting !== null}>{starting === action.jobType ? "Starting…" : action.label}</Button>)}
    </div>
    {message && <p className="text-right text-xs text-slate-500" role="status">{message}</p>}
  </div>;
}
