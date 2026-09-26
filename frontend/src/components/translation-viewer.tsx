"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiGet, apiPost, ApiError, toMessage } from "@/lib/api-client";
import { estimatedState, type ProcessingJob } from "@/lib/job";
import { translationLanguages } from "@/lib/languages";
import { formatTimestamp, type Transcript } from "@/lib/transcript";
import type { Translation } from "@/lib/translation";

type TranslationJobResponse = { job: ProcessingJob; translation: Translation };

export function TranslationViewer({ videoId, transcript }: { videoId: number; transcript: Transcript }) {
  const [targetLanguage, setTargetLanguage] = useState("es");
  const [translation, setTranslation] = useState<Translation | null>(null);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadTranslation = useCallback(async () => {
    try {
      setTranslation(await apiGet<Translation>(`/api/translations/video/${videoId}?target_language=${encodeURIComponent(targetLanguage)}`));
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setTranslation(null);
        return;
      }
      setError(toMessage(err, "Unable to load translation."));
    }
  }, [targetLanguage, videoId]);

  useEffect(() => {
    setJob(null);
    void loadTranslation();
  }, [loadTranslation]);

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "processing")) return;
    const interval = window.setInterval(async () => {
      let jobs: ProcessingJob[];
      try {
        jobs = await apiGet<ProcessingJob[]>(`/api/jobs/video/${videoId}`);
      } catch {
        return;
      }
      const current = jobs.find((item) => item.id === job.id);
      if (!current) return;
      setJob(current);
      if (current.status === "completed") void loadTranslation();
    }, 2000);
    return () => window.clearInterval(interval);
  }, [job, loadTranslation, videoId]);

  const targetName = useMemo(() => translationLanguages.find(([code]) => code === targetLanguage)?.[1] ?? targetLanguage, [targetLanguage]);
  const isRunning = job?.status === "queued" || job?.status === "processing";

  async function translate() {
    setError(null);
    try {
      const result = await apiPost<TranslationJobResponse>("/api/translations", { video_id: videoId, target_language: targetLanguage });
      setJob(result.job);
      setTranslation(result.translation.segments ? result.translation : null);
      if (result.job.status === "completed") void loadTranslation();
    } catch (err) {
      setError(toMessage(err, "Unable to start translation."));
    }
  }

  return <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-lg font-semibold">Translation</h2><p className="mt-1 text-sm text-slate-600">Create a timestamp-preserving translation in one of 60+ languages.</p></div><div className="flex flex-wrap items-center gap-2"><label className="sr-only" htmlFor="target-language">Target language</label><select id="target-language" className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)} disabled={isRunning}>{translationLanguages.map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select><Button onClick={() => void translate()} disabled={isRunning}>{isRunning ? "Translating…" : job?.status === "failed" ? "Retry translation" : `Translate to ${targetName}`}</Button></div></div>{job && <div className="mt-4 max-w-md" aria-live="polite"><div className="flex justify-between gap-3 text-xs text-slate-600"><span>{estimatedState(job)}</span><span>{job.progress}%</span></div><div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200"><div className={`h-full transition-all ${job.status === "failed" ? "bg-red-600" : "bg-slate-900"}`} style={{ width: `${job.progress}%` }} /></div>{job.error_message && <p className="mt-2 text-sm text-red-700" role="alert">{job.error_message}</p>}</div>}{error && <p className="mt-4 text-sm text-red-700" role="alert">{error}</p>}{translation?.segments && <div className="mt-6 overflow-x-auto"><div className="grid min-w-[640px] grid-cols-[120px_1fr_1fr] gap-x-4 border-b border-slate-200 pb-2 text-xs font-medium uppercase tracking-wide text-slate-500"><span>Time</span><span>{transcript.language}</span><span>{translation.target_language_name}</span></div><ol className="min-w-[640px] divide-y divide-slate-200">{transcript.segments.map((source, index) => <li key={`${source.start}-${index}`} className="grid grid-cols-[120px_1fr_1fr] gap-x-4 py-3 text-sm"><span className="font-mono text-slate-500">{formatTimestamp(source.start)}</span><p className="text-slate-800">{source.text}</p><p className="text-slate-800">{translation.segments?.[index]?.text ?? "—"}</p></li>)}</ol></div>}</section>;
}
