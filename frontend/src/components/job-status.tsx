"use client";

import { useEffect, useState } from "react";

import { estimatedState, type ProcessingJob } from "@/lib/job";

type JobStatusProps = { videoId: number };

export function JobStatus({ videoId }: JobStatusProps) {
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/api/jobs/video/${videoId}`, { cache: "no-store" });
        if (!response.ok) return;
        const jobs = (await response.json()) as ProcessingJob[];
        if (active) setJob(jobs[0] ?? null);
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
    </div>
  );
}
