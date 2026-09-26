"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api-client";
import { estimatedState, type ProcessingJob } from "@/lib/job";

type JobStatusProps = { videoId: number };

export function JobStatus({ videoId }: JobStatusProps) {
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const jobs = await apiGet<ProcessingJob[]>(`/api/jobs/video/${videoId}`);
        if (active) setJob(jobs[0] ?? null);
      } catch {
        // Keep the last known job on transient failures.
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    const interval = window.setInterval(() => void load(), 2000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [videoId]);

  if (isLoading) return <span className="text-xs text-slate-500">Checking status…</span>;
  if (!job) return <span className="text-xs text-slate-500">Upload complete · Not started</span>;

  const color = job.status === "failed" ? "bg-red-600" : job.status === "completed" ? "bg-green-600" : "bg-slate-900";
  return (
    <div className="min-w-40" aria-live="polite">
      <div className="flex justify-between gap-3 text-xs"><span className="capitalize text-slate-700">{job.status}</span><span className="text-slate-500">{job.progress}%</span></div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200"><div className={`h-full ${color} transition-all`} style={{ width: `${job.progress}%` }} /></div>
      <p className="mt-1 text-xs text-slate-500">{estimatedState(job)}{job.error_message ? ` · ${job.error_message}` : ""}</p>
      {job.has_output && (
        <a
          className="mt-1 inline-block text-xs font-medium text-slate-900 underline underline-offset-2"
          href={`/api/jobs/${job.id}/output`}
          download
        >
          Download {job.job_type === "autocrop" ? "vertical video" : "output"}
        </a>
      )}
    </div>
  );
}
