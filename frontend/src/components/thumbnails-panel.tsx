"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPost, toMessage } from "@/lib/api-client";
import type { ProcessingJob } from "@/lib/job";

type ThumbnailCandidate = {
  id: number;
  video_id: number;
  timestamp: number;
  score: number;
  width: number;
  height: number;
  selected: boolean;
};

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function ThumbnailsPanel({ videoId }: { videoId: number }) {
  const [count, setCount] = useState(8);
  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [candidates, setCandidates] = useState<ThumbnailCandidate[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [selecting, setSelecting] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshCandidates = useCallback(async () => {
    try {
      setCandidates(await apiGet<ThumbnailCandidate[]>(`/api/thumbnails/video/${videoId}`));
    } catch {
      /* keep previous list */
    }
  }, [videoId]);

  useEffect(() => {
    void refreshCandidates();
  }, [refreshCandidates]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed" || job.status === "cancelled") {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      if (job?.status === "completed") void refreshCandidates();
      return;
    }
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const updated = await apiGet<ProcessingJob>(`/api/jobs/${job.id}`);
        setJob(updated);
      } catch {
        /* transient; keep polling */
      }
    }, 2000);
  }, [job, refreshCandidates]);

  async function start() {
    setStarting(true);
    setMessage(null);
    try {
      const created = await apiPost<ProcessingJob>(`/api/thumbnails/generate/${videoId}`, { count });
      setJob(created);
      setMessage("Extracting and scoring thumbnail candidates…");
    } catch (error) {
      setMessage(toMessage(error, "Could not start thumbnail generation."));
    } finally {
      setStarting(false);
    }
  }

  async function selectCandidate(id: number) {
    setSelecting(id);
    try {
      await apiPost(`/api/thumbnails/${id}/select`);
      await refreshCandidates();
    } catch (error) {
      setMessage(toMessage(error, "Could not select the thumbnail."));
    } finally {
      setSelecting(null);
    }
  }

  const running = job !== null && !["completed", "failed", "cancelled"].includes(job.status);

  return (
    <div>
      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-slate-700">Candidates</span>
          <Input
            type="number"
            min={1}
            max={16}
            value={count}
            onChange={(event) => setCount(Number(event.target.value))}
            className="w-24"
          />
        </label>
        <Button onClick={() => void start()} disabled={starting || running}>
          {starting ? "Starting…" : running ? `Working… ${job?.progress ?? 0}%` : "Generate thumbnails"}
        </Button>
        {job?.status === "failed" && (
          <p className="text-sm text-red-600">Generation failed{job.error_message ? `: ${job.error_message}` : "."}</p>
        )}
      </div>

      {message && <p className="mt-4 text-sm text-slate-600">{message}</p>}

      {candidates.length > 0 && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {candidates.map((candidate) => (
            <figure
              key={candidate.id}
              className={`overflow-hidden rounded-lg border bg-white shadow-sm ${candidate.selected ? "border-green-500 ring-2 ring-green-200" : "border-slate-200"}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/api/thumbnails/${candidate.id}/image`}
                alt={`Thumbnail candidate at ${formatTime(candidate.timestamp)}`}
                className="aspect-video w-full object-cover"
                loading="lazy"
              />
              <figcaption className="flex items-center justify-between gap-2 p-3">
                <div className="text-sm">
                  <p className="font-medium text-slate-900">
                    {formatTime(candidate.timestamp)}
                    <span className="ml-2 text-slate-500">score {candidate.score.toFixed(2)}</span>
                  </p>
                  {candidate.selected && <p className="text-green-700">Current thumbnail</p>}
                </div>
                {!candidate.selected && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={selecting === candidate.id}
                    onClick={() => void selectCandidate(candidate.id)}
                  >
                    {selecting === candidate.id ? "Saving…" : "Use as thumbnail"}
                  </Button>
                )}
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      {candidates.length === 0 && !running && (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-600">
          No thumbnails yet. Generate candidates and pick the one that will sell the recap.
        </p>
      )}
    </div>
  );
}
