"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorMessage } from "@/components/ui/feedback";
import { Input } from "@/components/ui/input";
import { TranslationViewer } from "@/components/translation-viewer";
import { apiGet, apiPost, ApiError, toMessage } from "@/lib/api-client";
import { estimatedState, isTerminalStatus, type ProcessingJob } from "@/lib/job";
import { formatTimestamp, type Transcript } from "@/lib/transcript";

export function TranscriptViewer({ videoId }: { videoId: number }) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [copied, setCopied] = useState(false);
  const player = useRef<HTMLVideoElement>(null);

  const loadTranscript = useCallback(async () => {
    try {
      setTranscript(await apiGet<Transcript>(`/api/transcripts/${videoId}`));
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return;
      setError(toMessage(err, "Unable to load transcript."));
    }
  }, [videoId]);

  useEffect(() => { void loadTranscript(); }, [loadTranscript]);

  const loadedTranscriptForJob = useRef<number | null>(null);
  useEffect(() => {
    let active = true;
    async function loadJob() {
      let jobs: ProcessingJob[];
      try {
        jobs = await apiGet<ProcessingJob[]>(`/api/jobs/video/${videoId}`);
      } catch {
        return;
      }
      const transcription = jobs.find((item) => item.job_type === "transcription") ?? null;
      if (!active) return;
      setJob(transcription);
      if (transcription?.status === "completed" && loadedTranscriptForJob.current !== transcription.id) {
        loadedTranscriptForJob.current = transcription.id;
        void loadTranscript();
      }
    }
    void loadJob();
    // No active transcription: nothing to poll.
    if (!job || isTerminalStatus(job.status)) return () => { active = false; };
    const interval = window.setInterval(() => void loadJob(), 2000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [loadTranscript, videoId, job?.id, job?.status]);

  const visibleSegments = useMemo(
    () => transcript?.segments.filter((segment) => segment.text.toLowerCase().includes(search.toLowerCase())) ?? [],
    [search, transcript],
  );

  async function start() {
    setIsStarting(true);
    setError(null);
    try {
      setJob(await apiPost<ProcessingJob>(`/api/transcripts/${videoId}`));
    } catch (err) {
      setError(toMessage(err, "Unable to start transcription."));
    } finally {
      setIsStarting(false);
    }
  }

  async function copyText() {
    if (!transcript) return;
    await navigator.clipboard.writeText(transcript.full_text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  function seekTo(seconds: number) {
    if (!player.current) return;
    player.current.currentTime = seconds;
    void player.current.play().catch(() => undefined);
  }

  if (!transcript) {
    const isRunning = job?.status === "queued" || job?.status === "processing";
    return <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Transcript unavailable</h2><p className="mt-2 text-sm text-slate-600">Start a transcription job to generate searchable timestamps and text.</p>{job && <div className="mt-4" aria-live="polite"><div className="flex max-w-md justify-between gap-3 text-xs text-slate-600"><span>{estimatedState(job)}</span><span>{job.progress}%</span></div><div className="mt-1 h-1.5 max-w-md overflow-hidden rounded-full bg-slate-200"><div className={`h-full transition-all ${job.status === "failed" ? "bg-red-600" : "bg-slate-900"}`} style={{ width: `${job.progress}%` }} /></div>{job.error_message && <p className="mt-2 text-sm text-red-700" role="alert">{job.error_message}</p>}</div>}{error && <div className="mt-4"><ErrorMessage>{error}</ErrorMessage></div>}<Button className="mt-5" onClick={start} disabled={isStarting || isRunning}>{isStarting ? "Starting…" : isRunning ? "Transcription in progress" : "Start transcription"}</Button></section>;
  }

  return <section className="space-y-6"><div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Video</h2><p className="mt-1 text-sm text-slate-600">Choose a timestamp below to jump to that moment.</p><video ref={player} className="mt-4 w-full rounded-md bg-slate-950" controls preload="metadata" src={`/api/videos/${videoId}/playback`}>Your browser does not support video playback.</video></div><div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-lg font-semibold">Full transcript</h2><p className="mt-1 text-sm text-slate-600">Detected language: {transcript.language}</p></div><Button variant="outline" onClick={copyText}>{copied ? "Copied" : "Copy transcript"}</Button></div><p className="mt-5 whitespace-pre-wrap leading-7 text-slate-800">{transcript.full_text}</p></div><TranslationViewer videoId={videoId} transcript={transcript} /><div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Timestamps</h2><Input className="mt-4" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search transcript" aria-label="Search transcript" /><ol className="mt-4 divide-y divide-slate-200">{visibleSegments.map((segment, index) => <li key={`${segment.start}-${index}`} className="flex gap-4 py-3"><Button className="shrink-0 font-mono" variant="outline" size="sm" onClick={() => seekTo(segment.start)} aria-label={`Play from ${formatTimestamp(segment.start)}`}>{formatTimestamp(segment.start)}</Button><p className="pt-1 text-sm leading-6 text-slate-800">{segment.text}</p></li>)}{visibleSegments.length === 0 && <li className="py-3 text-sm text-slate-500">No matching segments.</li>}</ol></div></section>;
}
