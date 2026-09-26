"use client";

import { useCallback, useEffect, useState } from "react";

import { useJobPolling } from "@/lib/use-job-polling";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorMessage } from "@/components/ui/feedback";
import { apiGet, apiPost, toMessage } from "@/lib/api-client";
import type { ProcessingJob } from "@/lib/job";

type Beat = { timestamp: number; heading: string; summary: string };
type Quote = { timestamp: number; text: string };
type DraftContent = {
  titles: string[];
  hook: string;
  beats: Beat[];
  key_quotes: Quote[];
};

type RecapDraft = {
  id: number;
  video_id: number;
  job_id: number;
  content: DraftContent;
  model: string;
  created_at: string | null;
};

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function DraftView({ draft }: { draft: RecapDraft }) {
  const [copied, setCopied] = useState(false);
  const { content } = draft;

  async function copyScript() {
    const lines = [
      ...content.titles.map((title, index) => `TITLE ${index + 1}: ${title}`),
      "",
      `HOOK: ${content.hook}`,
      "",
      ...content.beats.flatMap((beat) => [
        `[${formatTime(beat.timestamp)}] ${beat.heading}`,
        beat.summary,
        "",
      ]),
      "KEY QUOTES:",
      ...content.key_quotes.map((quote) => `[${formatTime(quote.timestamp)}] "${quote.text}"`),
    ];
    await navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Title ideas</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-800">
            {content.titles.map((title) => (
              <li key={title}>{title}</li>
            ))}
          </ul>
        </div>
        <Button variant="outline" size="sm" onClick={() => void copyScript()}>
          {copied ? "Copied!" : "Copy script"}
        </Button>
      </div>

      <h2 className="mt-6 text-lg font-semibold">Hook</h2>
      <p className="mt-2 rounded-md bg-slate-50 p-3 text-slate-800">{content.hook}</p>

      <h2 className="mt-6 text-lg font-semibold">Story beats</h2>
      <ol className="mt-2 space-y-4">
        {content.beats.map((beat, index) => (
          <li key={index} className="border-l-2 border-slate-200 pl-4">
            <p className="font-medium text-slate-900">
              <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
                {formatTime(beat.timestamp)}
              </span>
              {beat.heading}
            </p>
            <p className="mt-1 text-slate-700">{beat.summary}</p>
          </li>
        ))}
      </ol>

      {content.key_quotes.length > 0 && (
        <>
          <h2 className="mt-6 text-lg font-semibold">Key quotes</h2>
          <ul className="mt-2 space-y-2">
            {content.key_quotes.map((quote, index) => (
              <li key={index} className="text-slate-700">
                <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
                  {formatTime(quote.timestamp)}
                </span>
                &ldquo;{quote.text}&rdquo;
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="mt-6 text-xs text-slate-400">
        Drafted by {draft.model}
        {draft.created_at ? ` on ${new Date(draft.created_at).toLocaleString()}` : ""}. Review and
        rewrite in your own voice before publishing.
      </p>
    </article>
  );
}

export function AssistantPanel({ videoId }: { videoId: number }) {
  const [drafts, setDrafts] = useState<RecapDraft[]>([]);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refreshDrafts = useCallback(async () => {
    try {
      setDrafts(await apiGet<RecapDraft[]>(`/api/assistant/recap/video/${videoId}`));
    } catch {
      /* keep previous list */
    }
  }, [videoId]);

  useEffect(() => {
    void refreshDrafts();
  }, [refreshDrafts]);


  useJobPolling(job, setJob, useCallback(() => {
    void refreshDrafts();
  }, [refreshDrafts]));

  async function start() {
    setStarting(true);
    setMessage(null);
    try {
      const created = await apiPost<ProcessingJob>(`/api/assistant/recap/${videoId}`);
      setJob(created);
      setMessage("Drafting your recap script…");
    } catch (error) {
      setMessage(toMessage(error, "Could not start the recap draft."));
    } finally {
      setStarting(false);
    }
  }

  const running = job !== null && !["completed", "failed", "cancelled"].includes(job.status);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <p className="flex-1 text-sm text-slate-600">
          Needs a finished transcript and <code className="rounded bg-slate-100 px-1">OPENAI_API_KEY</code> on
          the server. The draft is a starting point — always rewrite it in your own voice.
        </p>
        <Button onClick={() => void start()} disabled={starting || running}>
          {starting ? "Starting…" : running ? `Drafting… ${job?.progress ?? 0}%` : drafts.length > 0 ? "Draft again" : "Draft recap script"}
        </Button>
      </div>

      {message && <p className="mt-4 text-sm text-slate-600">{message}</p>}
      {job?.status === "failed" && (
        <div className="mt-4">
          <ErrorMessage>Drafting failed{job.error_message ? `: ${job.error_message}` : "."}</ErrorMessage>
        </div>
      )}

      <div className="mt-6 grid gap-6">
        {drafts.map((draft) => (
          <DraftView key={draft.id} draft={draft} />
        ))}
      </div>

      {drafts.length === 0 && !running && (
        <div className="mt-6">
          <EmptyState>No drafts yet. Generate one from the transcript and it will appear here.</EmptyState>
        </div>
      )}
    </div>
  );
}
