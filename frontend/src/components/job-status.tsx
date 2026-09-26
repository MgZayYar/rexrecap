"use client";

import { useState } from "react";

import { apiPost } from "@/lib/api-client";
import { estimatedState, type ProcessingJob } from "@/lib/job";

type JobStatusProps = {
  job: ProcessingJob | null;
  onChanged: () => void;
};

/** Presentational job row. Polling is owned by the parent (one request for
 *  all videos) so N dashboard rows don't each run their own poller. */
export function JobStatus({ job, onChanged }: JobStatusProps) {
  const [isActing, setIsActing] = useState(false);

  async function act(action: "cancel" | "retry") {
    if (!job || isActing) return;
    setIsActing(true);
    try {
      await apiPost<ProcessingJob>(`/api/jobs/${job.id}/${action}`);
      onChanged();
    } catch {
      // Leave the last known state; the next poll will correct it.
    } finally {
      setIsActing(false);
    }
  }

  if (!job) return <span className="text-xs text-slate-500">Upload complete · Not started</span>;

  const color = job.status === "failed" ? "bg-red-600" : job.status === "completed" ? "bg-green-600" : "bg-slate-900";
  const canCancel = job.status === "queued" || (job.status === "processing" && !job.cancel_requested);
  const canRetry = job.status === "failed" || job.status === "cancelled";
  return (
    <div className="min-w-40" aria-live="polite">
      <div className="flex justify-between gap-3 text-xs"><span className="capitalize text-slate-700">{job.status}</span><span className="text-slate-500">{job.progress}%</span></div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200"><div className={`h-full ${color} transition-all`} style={{ width: `${job.progress}%` }} /></div>
      <p className="mt-1 text-xs text-slate-500">{estimatedState(job)}{job.error_message ? ` · ${job.error_message}` : ""}</p>
      <div className="mt-1 flex items-center gap-3">
        {job.has_output && (
          <a
            className="text-xs font-medium text-slate-900 underline underline-offset-2"
            href={`/api/jobs/${job.id}/output`}
            download
          >
            Download {job.job_type === "autocrop" ? "vertical video" : "output"}
          </a>
        )}
        {canCancel && (
          <button type="button" disabled={isActing} onClick={() => void act("cancel")}
            className="text-xs font-medium text-red-700 underline underline-offset-2 disabled:opacity-50">
            Cancel
          </button>
        )}
        {canRetry && (
          <button type="button" disabled={isActing} onClick={() => void act("retry")}
            className="text-xs font-medium text-slate-900 underline underline-offset-2 disabled:opacity-50">
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
