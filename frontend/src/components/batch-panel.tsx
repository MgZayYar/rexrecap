"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPost, toMessage } from "@/lib/api-client";
import { formatFileSize, type Video } from "@/lib/video";

const BATCHABLE_JOBS: { value: string; label: string }[] = [
  { value: "transcription", label: "Transcription" },
  { value: "translation", label: "Translation" },
  { value: "dubbing", label: "Dubbing" },
  { value: "autocrop", label: "Autocrop" },
  { value: "face_detection", label: "Face detection" },
  { value: "subtitle_burn", label: "Burn subtitles" },
  { value: "render", label: "Render" },
  { value: "shorts", label: "Highlight clips" },
  { value: "thumbnails", label: "Thumbnails" },
  { value: "recap", label: "Recap draft" },
];

type BatchSummary = {
  status: string;
  total: number;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
  cancelled: number;
};

type BatchRun = {
  id: number;
  label: string;
  job_type: string;
  created_at: string | null;
  summary: BatchSummary;
};

type BatchItem = {
  video_id: number;
  filename: string;
  job_id: number;
  job_status: string;
  job_progress: number;
};

type BatchDetail = BatchRun & { items: BatchItem[] };

function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "bg-green-50 text-green-700";
    case "failed":
      return "bg-red-50 text-red-700";
    case "cancelled":
      return "bg-slate-100 text-slate-600";
    case "processing":
      return "bg-blue-50 text-blue-700";
    default:
      return "bg-amber-50 text-amber-700";
  }
}

export function BatchPanel() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [jobType, setJobType] = useState("transcription");
  const [label, setLabel] = useState("");
  const [batches, setBatches] = useState<BatchRun[]>([]);
  const [expanded, setExpanded] = useState<Record<number, BatchDetail>>({});
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [videoList, batchList] = await Promise.all([
        apiGet<Video[]>("/api/videos"),
        apiGet<BatchRun[]>("/api/batch/runs"),
      ]);
      setVideos(videoList);
      setBatches(batchList);
    } catch {
      /* keep previous state */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  function toggleVideo(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function startBatch() {
    if (selected.size === 0) {
      setMessage("Select at least one video first.");
      return;
    }
    setStarting(true);
    setMessage(null);
    try {
      await apiPost("/api/batch/runs", {
        job_type: jobType,
        video_ids: [...selected],
        label: label.trim() || undefined,
      });
      setSelected(new Set());
      setLabel("");
      setMessage(`Queued ${jobType} for ${selected.size} video${selected.size === 1 ? "" : "s"}.`);
      await refresh();
    } catch (error) {
      setMessage(toMessage(error, "Could not start the batch run."));
    } finally {
      setStarting(false);
    }
  }

  async function toggleDetail(batchId: number) {
    if (expanded[batchId]) {
      setExpanded((prev) => {
        const next = { ...prev };
        delete next[batchId];
        return next;
      });
      return;
    }
    try {
      const detail = await apiGet<BatchDetail>(`/api/batch/runs/${batchId}`);
      setExpanded((prev) => ({ ...prev, [batchId]: detail }));
    } catch {
      /* keep collapsed */
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <section>
        <h2 className="text-xl font-semibold">Start a batch</h2>
        <p className="mt-1 text-sm text-slate-600">
          Queue the same job across many videos at once. Each video gets its own job, tracked below as a group.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <label className="grid gap-1 text-sm">
            <span className="font-medium text-slate-700">Job</span>
            <select
              value={jobType}
              onChange={(event) => setJobType(event.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              {BATCHABLE_JOBS.map((job) => (
                <option key={job.value} value={job.value}>
                  {job.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            <span className="font-medium text-slate-700">Label (optional)</span>
            <Input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Weekly recaps" className="w-48" />
          </label>
          <Button onClick={() => void startBatch()} disabled={starting || selected.size === 0}>
            {starting ? "Queueing…" : `Run on ${selected.size} video${selected.size === 1 ? "" : "s"}`}
          </Button>
        </div>
        {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          {videos.length === 0 ? (
            <p className="p-6 text-center text-slate-600">No videos uploaded yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {videos.map((video) => (
                <li key={video.id}>
                  <label className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={selected.has(video.id)}
                      onChange={() => toggleVideo(video.id)}
                      className="h-4 w-4 accent-slate-900"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-slate-900">{video.filename}</span>
                      <span className="text-xs text-slate-500">{formatFileSize(video.size_bytes)}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold">Batch runs</h2>
        <p className="mt-1 text-sm text-slate-600">Progress across the group. Open a run for per-video status.</p>
        <div className="mt-4 grid gap-3">
          {batches.length === 0 && (
            <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-600">
              No batch runs yet.
            </p>
          )}
          {batches.map((batch) => {
            const done = batch.summary.completed + batch.summary.failed + batch.summary.cancelled;
            const percent = batch.summary.total === 0 ? 0 : Math.round((done / batch.summary.total) * 100);
            return (
              <div key={batch.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-900">{batch.label}</p>
                    <p className="text-xs text-slate-500">
                      {batch.job_type} · {done}/{batch.summary.total} done
                      {batch.summary.failed > 0 && ` · ${batch.summary.failed} failed`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColor(batch.summary.status)}`}>
                      {batch.summary.status}
                    </span>
                    <Button size="sm" variant="outline" onClick={() => void toggleDetail(batch.id)}>
                      {expanded[batch.id] ? "Hide" : "Details"}
                    </Button>
                  </div>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-slate-900 transition-all" style={{ width: `${percent}%` }} />
                </div>
                {expanded[batch.id] && (
                  <ul className="mt-3 divide-y divide-slate-100 border-t border-slate-100">
                    {expanded[batch.id].items.map((item) => (
                      <li key={item.job_id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <span className="min-w-0 flex-1 truncate text-slate-800">{item.filename}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(item.job_status)}`}>
                          {item.job_status}
                          {item.job_status === "processing" ? ` ${item.job_progress}%` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
