"use client";

import { useState } from "react";

import { ProjectPicker } from "@/components/project-picker";
import { apiPatch, toMessage } from "@/lib/api-client";
import type { Video } from "@/lib/video";

/** Assign/move/unassign a video's project from the dashboard table. */
export function VideoProjectAssign({ video }: { video: Video }) {
  const [projectId, setProjectId] = useState<number | null>(video.project_id);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function assign(next: number | null) {
    setSaving(true);
    setError(null);
    try {
      const updated = await apiPatch<Video>(`/api/videos/${video.id}`, { project_id: next });
      setProjectId(updated.project_id);
    } catch (err) {
      setError(toMessage(err, "Could not update the project."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className="inline-flex flex-col gap-1">
      <ProjectPicker
        value={projectId}
        onChange={(next) => void assign(next)}
        disabled={saving}
        ariaLabel={`Project for ${video.filename}`}
      />
      {error && <span className="text-xs text-red-600" role="alert">{error}</span>}
    </span>
  );
}
