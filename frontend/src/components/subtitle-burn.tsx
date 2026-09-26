"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { apiPost, toMessage } from "@/lib/api-client";

type Source = "transcript" | "translation";
type Format = "ass" | "srt";

export function SubtitleBurn({ videoId }: { videoId: number }) {
  const [source, setSource] = useState<Source>("transcript");
  const [format, setFormat] = useState<Format>("ass");
  const [language, setLanguage] = useState("");
  const [burning, setBurning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function burn() {
    setBurning(true);
    setMessage(null);
    try {
      await apiPost(`/api/subtitles/burn/${videoId}`, {
        source,
        format,
        language: source === "translation" ? language.trim().toLowerCase() || null : null,
      });
      setMessage("Subtitle burn queued. Download it from the job list when it finishes.");
    } catch (err) {
      setMessage(toMessage(err, "Unable to start the subtitle burn."));
    } finally {
      setBurning(false);
    }
  }

  return <section className="rounded-lg border border-slate-200 bg-white p-5">
    <h2 className="text-xl font-semibold">Burn subtitles</h2>
    <p className="mt-1 text-sm text-slate-600">
      Render subtitles permanently into the video with FFmpeg. Uses the saved transcript or a translation.
    </p>
    <div className="mt-4 grid gap-3 sm:grid-cols-3">
      <label className="text-xs font-medium text-slate-600">Source
        <select className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" value={source} onChange={(event) => setSource(event.target.value as Source)} disabled={burning}>
          <option value="transcript">Transcript</option>
          <option value="translation">Translation</option>
        </select>
      </label>
      {source === "translation" && (
        <label className="text-xs font-medium text-slate-600">Language code
          <input className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="es" disabled={burning} />
        </label>
      )}
      <label className="text-xs font-medium text-slate-600">Format
        <select className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" value={format} onChange={(event) => setFormat(event.target.value as Format)} disabled={burning}>
          <option value="ass">ASS (styled)</option>
          <option value="srt">SRT (plain)</option>
        </select>
      </label>
    </div>
    <div className="mt-4">
      <Button size="sm" onClick={() => void burn()} disabled={burning}>{burning ? "Queuing…" : "Burn into video"}</Button>
    </div>
    {message && <p className="mt-3 text-xs text-slate-500" role="status">{message}</p>}
  </section>;
}
