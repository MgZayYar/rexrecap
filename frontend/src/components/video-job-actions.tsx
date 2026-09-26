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

const autocropRatios = ["9:16", "1:1", "4:5"] as const;
type AutocropRatio = (typeof autocropRatios)[number];

export function VideoJobActions({ videoId }: { videoId: number }) {
  const [starting, setStarting] = useState<ProcessingJob["job_type"] | null>(null);
  const [ratio, setRatio] = useState<AutocropRatio>("9:16");
  const [message, setMessage] = useState<string | null>(null);

  async function start(jobType: ProcessingJob["job_type"]) {
    setStarting(jobType);
    setMessage(null);
    try {
      const params = jobType === "autocrop" ? { aspect_ratio: ratio } : undefined;
      await apiPost("/api/jobs", { video_id: videoId, job_type: jobType, params });
      const label = actions.find((action) => action.jobType === jobType)?.label;
      setMessage(jobType === "autocrop" ? `${label} (${ratio}) job queued.` : `${label} job queued.`);
    } catch (err) {
      setMessage(toMessage(err, "Unable to start job."));
    } finally {
      setStarting(null);
    }
  }

  return <div className="space-y-2">
    <div className="flex flex-wrap items-center justify-end gap-2">
      {actions.map((action) => action.jobType === "autocrop" ? (
        <span key={action.jobType} className="inline-flex items-center gap-1">
          <select
            aria-label="Auto-crop aspect ratio"
            value={ratio}
            onChange={(event) => setRatio(event.target.value as AutocropRatio)}
            disabled={starting !== null}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
          >
            {autocropRatios.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <Button variant="outline" size="sm" onClick={() => void start(action.jobType)} disabled={starting !== null}>{starting === action.jobType ? "Starting…" : action.label}</Button>
        </span>
      ) : (
        <Button key={action.jobType} variant="outline" size="sm" onClick={() => void start(action.jobType)} disabled={starting !== null}>{starting === action.jobType ? "Starting…" : action.label}</Button>
      ))}
    </div>
    {message && <p className="text-right text-xs text-slate-500" role="status">{message}</p>}
  </div>;
}
