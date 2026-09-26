"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPost, toMessage } from "@/lib/api-client";

type Voice = { id: string; name: string; language: string; gender: string; provider: string };
type Transcript = { language: string | null };

export function DubbingPanel({ videoId }: { videoId: number }) {
  const [providers, setProviders] = useState<string[]>([]);
  const [provider, setProvider] = useState("edge");
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voice, setVoice] = useState("");
  const [language, setLanguage] = useState("en");
  const [targetLanguage, setTargetLanguage] = useState("");
  const [previewText, setPreviewText] = useState("Hello! This is a preview of the dubbing voice.");
  const [previewing, setPreviewing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [providerList, transcript] = await Promise.all([
          apiGet<string[]>("/api/dubbings/providers"),
          apiGet<Transcript>(`/api/transcripts/${videoId}`).catch(() => null),
        ]);
        if (!active) return;
        setProviders(providerList);
        if (transcript?.language) setLanguage(transcript.language.slice(0, 2).toLowerCase());
      } catch {
        if (active) setProviders(["edge"]);
      }
    })();
    return () => { active = false; };
  }, [videoId]);

  const loadVoices = useCallback(async (prov: string, lang: string) => {
    try {
      const list = await apiGet<Voice[]>(`/api/dubbings/voices?provider=${encodeURIComponent(prov)}&language=${encodeURIComponent(lang)}`);
      setVoices(list);
      setVoice((current) => (list.some((v) => v.id === current) ? current : (list[0]?.id ?? "")));
    } catch {
      setVoices([]);
    }
  }, []);

  useEffect(() => { void loadVoices(provider, language); }, [provider, language, loadVoices]);

  async function preview() {
    if (!voice || previewing) return;
    setPreviewing(true);
    setMessage(null);
    try {
      const response = await fetch("/api/dubbings/preview", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: previewText, voice, provider }),
      });
      if (!response.ok) throw new Error("Preview failed");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        void audioRef.current.play();
      }
    } catch (err) {
      setMessage(toMessage(err, "Unable to preview voice."));
    } finally {
      setPreviewing(false);
    }
  }

  async function start() {
    if (starting) return;
    setStarting(true);
    setMessage(null);
    try {
      await apiPost(`/api/dubbings/start/${videoId}`, {
        provider,
        voice: voice || null,
        target_language: targetLanguage.trim() || null,
      });
      setMessage("Dubbing job queued. Track progress on the dashboard.");
    } catch (err) {
      setMessage(toMessage(err, "Unable to start dubbing."));
    } finally {
      setStarting(false);
    }
  }

  const field = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm";

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Provider</span>
          <select className={field} value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providers.map((p) => <option key={p} value={p}>{p === "edge" ? "Edge (free)" : p}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Voice language</span>
          <Input value={language} maxLength={8} onChange={(e) => setLanguage(e.target.value.toLowerCase())} placeholder="en" />
        </label>
      </div>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Voice</span>
        <select className={field} value={voice} onChange={(e) => setVoice(e.target.value)}>
          {voices.length === 0 && <option value="">No voices found</option>}
          {voices.map((v) => <option key={v.id} value={v.id}>{v.name}{v.gender ? ` (${v.gender})` : ""}</option>)}
        </select>
        <span className="mt-1 block text-xs text-slate-500">Speaker A uses this voice; speaker B gets a contrasting one automatically.</span>
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Preview text</span>
        <div className="flex gap-2">
          <Input value={previewText} maxLength={300} onChange={(e) => setPreviewText(e.target.value)} />
          <Button type="button" variant="outline" onClick={() => void preview()} disabled={previewing || !voice}>
            {previewing ? "Playing…" : "Preview"}
          </Button>
        </div>
      </label>
      <audio ref={audioRef} className="hidden" />

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Dub language (optional)</span>
        <Input value={targetLanguage} maxLength={16} onChange={(e) => setTargetLanguage(e.target.value.toLowerCase())} placeholder="Leave empty for the transcript language" />
        <span className="mt-1 block text-xs text-slate-500">To dub a translation, enter its language code — the translation must already exist.</span>
      </label>

      <div className="flex items-center gap-3">
        <Button onClick={() => void start()} disabled={starting || !voice}>
          {starting ? "Starting…" : "Start dubbing"}
        </Button>
        {message && <p className="text-sm text-slate-600" role="status">{message}</p>}
      </div>
    </div>
  );
}
