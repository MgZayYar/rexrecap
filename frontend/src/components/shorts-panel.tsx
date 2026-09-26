"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPost, toMessage } from "@/lib/api-client";
import type { ProcessingJob } from "@/lib/job";

type ShortClip = {
  id: number;
  video_id: number;
  job_id: number;
  start_time: number;
  end_time: number;
  score: number;
  duration: number;
};

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function ShortsPanel({ videoId }: { videoId: number }) {
  const [count, setCount] = useState(3);
  const [clipDuration, setClipDuration] = useState(30);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [clips, setClips] = useState<ShortClip[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshClips = useCallback(async () => {
    try {
      setClips(await apiGet<ShortClip[]>(`/api/shorts/video/${videoId}`));
    } catch {
      /* keep previous list */
    }
  }, [videoId]);

  useEffect(() => {
    void refreshClips();
  }, [refreshClips]);

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
      if (job?.status === "completed") void refreshClips();
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
  }, [job, refreshClips]);

  async function start() {
    setStarting(true);
    setMessage(null);
    try {
      const created = await apiPost<ProcessingJob>(`/api/shorts/generate/${videoId}`, {
        count,
        clip_duration: clipDuration,
        aspect_ratio: aspectRatio,
        burn_subtitles: burnSubtitles ? "srt" : null,
        subtitle_source: "transcript",
      });
      setJob(created);
      setMessage("Detecting highlight moments and cutting clips…");
    } catch (error) {
      setMessage(toMessage(error, "Could not start clip generation."));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Number of clips (1–10)</span>
          <Input type="number" min={1} max={10} value={count}
                 onChange={(e) => setCount(Math.min(10, Math.max(1, Number(e.target.value) || 1)))} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Clip length, seconds (5–180)</span>
          <Input type="number" min={5} max={180} value={clipDuration}
                 onChange={(e) => setClipDuration(Math.min(180, Math.max(5, Number(e.target.value) || 30)))} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Aspect ratio</span>
          <select className="w-full rounded-md border px-3 py-2 text-sm"
                  value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
            <option value="9:16">9:16 (Shorts / Reels / TikTok)</option>
            <option value="1:1">1:1 (square)</option>
            <option value="4:5">4:5 (portrait)</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={burnSubtitles}
                 onChange={(e) => setBurnSubtitles(e.target.checked)} />
          Burn subtitles into clips
        </label>
      </div>

      <Button onClick={start} disabled={starting}>
        {starting ? "Starting…" : "Generate highlight clips"}
      </Button>

      {message && <p className="text-sm text-slate-600">{message}</p>}

      {job && job.status !== "completed" && (
        <div className="rounded-lg border p-4 text-sm">
          <p className="font-medium capitalize">Job {job.status} — {job.progress}%</p>
          <div className="mt-2 h-2 w-full rounded bg-slate-200">
            <div className="h-2 rounded bg-blue-600" style={{ width: `${job.progress}%` }} />
          </div>
        </div>
      )}

      {clips.length > 0 && (
        <div>
          <h2 className="mb-3 text-xl font-semibold">Clips ({clips.length})</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {clips.map((clip) => (
              <div key={clip.id} className="overflow-hidden rounded-lg border">
                <video className="aspect-[9/16] w-full bg-black" controls preload="metadata"
                       src={`/api/shorts/${clip.id}/download`} />
                <div className="p-3 text-sm">
                  <p className="font-medium">
                    {formatTime(clip.start_time)} → {formatTime(clip.end_time)}
                    <span className="ml-2 text-slate-500">score {clip.score.toFixed(2)}</span>
                  </p>
                  <a className="mt-1 inline-block font-medium text-blue-700 underline"
                     href={`/api/shorts/${clip.id}/download`} download>
                    Download MP4
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
