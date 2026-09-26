"use client";

import { useEffect, useRef } from "react";

import { apiGet } from "@/lib/api-client";
import { isTerminalStatus, type ProcessingJob } from "@/lib/job";

const DEFAULT_INTERVAL_MS = 2000;

/** Poll a single job until it reaches a terminal state.
 *
 * Replaces the hand-rolled poller that every workflow panel duplicated:
 * set the job, and this hook refreshes it every `intervalMs` until it is
 * terminal, then fires `onTerminal` once per job. Unmounting always clears
 * the timer.
 */
export function useJobPolling(
  job: ProcessingJob | null,
  setJob: (job: ProcessingJob) => void,
  onTerminal: () => void,
  intervalMs: number = DEFAULT_INTERVAL_MS
): void {
  const onTerminalRef = useRef(onTerminal);
  onTerminalRef.current = onTerminal;
  const firedForRef = useRef<number | null>(null);

  useEffect(() => {
    if (!job) return;
    if (isTerminalStatus(job.status)) {
      if (firedForRef.current !== job.id) {
        firedForRef.current = job.id;
        onTerminalRef.current();
      }
      return;
    }
    firedForRef.current = null;
    const timer = window.setInterval(async () => {
      try {
        const updated = await apiGet<ProcessingJob>(`/api/jobs/${job.id}`);
        setJob(updated);
      } catch {
        // Transient failure; the next tick retries.
      }
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status, intervalMs, setJob]);
}
