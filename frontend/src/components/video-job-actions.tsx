"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { apiPost, toMessage } from "@/lib/api-client";
import type { ProcessingJob } from "@/lib/job";

const actions: Array<{ jobType: ProcessingJob["job_type"]; label: string }> = [
  { jobType: "transcription", label: "Transcribe" },
  { jobType: "dubbing", label: "Dub" },
  { jobType: "autocrop", label: "Auto-crop" },
  { jobType: "render", label: "Render" },
];

const autocropRatios = ["9:16", "1:1", "4:5"] as const;
type AutocropRatio = (typeof autocropRatios)[number];

const renderRatios = ["off", "9:16", "1:1", "4:5"] as const;
type RenderRatio = (typeof renderRatios)[number];
const renderSubtitleFormats = ["off", "ass", "srt"] as const;
type RenderSubtitleFormat = (typeof renderSubtitleFormats)[number];

export function VideoJobActions({ videoId, onJobStarted }: { videoId: number; onJobStarted?: () => void }) {
  const [starting, setStarting] = useState<ProcessingJob["job_type"] | null>(null);
  const [ratio, setRatio] = useState<AutocropRatio>("9:16");
  const [renderRatio, setRenderRatio] = useState<RenderRatio>("off");
  const [renderSubs, setRenderSubs] = useState<RenderSubtitleFormat>("off");
  const [renderDubbed, setRenderDubbed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function start(jobType: ProcessingJob["job_type"]) {
    setStarting(jobType);
    setMessage(null);
    try {
      let params: Record<string, unknown> | undefined;
      if (jobType === "autocrop") {
        params = { aspect_ratio: ratio };
      } else if (jobType === "render") {
        params = {
          aspect_ratio: renderRatio === "off" ? null : renderRatio,
          burn_subtitles: renderSubs === "off" ? null : renderSubs,
          subtitle_source: "transcript",
          use_dubbed_audio: renderDubbed,
        };
      }
      await apiPost("/api/jobs", { video_id: videoId, job_type: jobType, params });
      const label = actions.find((action) => action.jobType === jobType)?.label;
      const detail = jobType === "autocrop" ? ` (${ratio})` : "";
      setMessage(`${label}${detail} job queued.`);
      onJobStarted?.();
    } catch (err) {
      setMessage(toMessage(err, "Unable to start job."));
    } finally {
      setStarting(null);
    }
  }

  return <div className="space-y-2">
    <div className="flex flex-wrap items-center justify-end gap-2">
      {actions.map((action) => action.jobType === "autocrop" ? (
        <span key={action.jobType} className="inline-flex items-center gap-1">
          <select
            aria-label="Auto-crop aspect ratio"
            value={ratio}
            onChange={(event) => setRatio(event.target.value as AutocropRatio)}
            disabled={starting !== null}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
          >
            {autocropRatios.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <Button variant="outline" size="sm" onClick={() => void start(action.jobType)} disabled={starting !== null}>{starting === action.jobType ? "Starting…" : action.label}</Button>
        </span>
      ) : action.jobType === "render" ? (
        <span key={action.jobType} className="inline-flex items-center gap-1" title="Assemble the final MP4: smart-crop, burned subtitles, dubbed audio">
          <select
            aria-label="Render aspect ratio"
            value={renderRatio}
            onChange={(event) => setRenderRatio(event.target.value as RenderRatio)}
            disabled={starting !== null}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
          >
            {renderRatios.map((value) => <option key={value} value={value}>{value === "off" ? "Crop off" : value}</option>)}
          </select>
          <select
            aria-label="Render subtitles"
            value={renderSubs}
            onChange={(event) => setRenderSubs(event.target.value as RenderSubtitleFormat)}
            disabled={starting !== null}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
          >
            {renderSubtitleFormats.map((value) => <option key={value} value={value}>{value === "off" ? "Subs off" : value.toUpperCase()}</option>)}
          </select>
          <label className="inline-flex items-center gap-1 text-xs text-slate-600">
            <input
              type="checkbox"
              aria-label="Use dubbed audio"
              checked={renderDubbed}
              onChange={(event) => setRenderDubbed(event.target.checked)}
              disabled={starting !== null}
              className="h-3.5 w-3.5"
            />
            Dubbed audio
          </label>
          <Button variant="outline" size="sm" onClick={() => void start(action.jobType)} disabled={starting !== null}>{starting === action.jobType ? "Starting…" : action.label}</Button>
        </span>
      ) : (
        <Button key={action.jobType} variant="outline" size="sm" onClick={() => void start(action.jobType)} disabled={starting !== null}>{starting === action.jobType ? "Starting…" : action.label}</Button>
      ))}
    </div>
    {message && <p className="text-right text-xs text-slate-500" role="status">{message}</p>}
  </div>;
}
