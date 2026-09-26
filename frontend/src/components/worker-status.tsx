"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api-client";
import type { WorkerInfo } from "@/lib/job";

/** Small badge showing whether any worker process is alive. */
export function WorkerStatus() {
  const [workers, setWorkers] = useState<WorkerInfo[] | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await apiGet<WorkerInfo[]>("/api/jobs/workers");
        if (active) setWorkers(data);
      } catch {
        if (active) setWorkers([]);
      }
    }
    void load();
    const interval = window.setInterval(() => void load(), 5000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  if (workers === null) return null;
  const live = workers.filter((w) => w.is_live);
  const busy = live.find((w) => w.current_job_id !== null);
  const online = live.length > 0;
  return (
    <span
      title={online ? `${live.length} worker(s) running${busy ? ` · job ${busy.current_job_id} in progress` : ""}` : "No worker process detected — start one with: python -m app.workers.runner"}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${online ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}
    >
      <span className={`h-2 w-2 rounded-full ${online ? "bg-green-600" : "bg-amber-500"}`} aria-hidden />
      {online ? `Worker online${busy ? " · busy" : ""}` : "Worker offline"}
    </span>
  );
}
