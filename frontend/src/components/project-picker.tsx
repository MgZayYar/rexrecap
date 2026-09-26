"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api-client";
import type { Project } from "@/lib/video";

type ProjectPickerProps = {
  value: number | null;
  onChange: (projectId: number | null) => void;
  disabled?: boolean;
  ariaLabel: string;
};

/** Dropdown of the user's projects, including an "unassigned" option. */
export function ProjectPicker({ value, onChange, disabled, ariaLabel }: ProjectPickerProps) {
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<Project[]>("/api/projects")
      .then((loaded) => { if (!cancelled) setProjects(loaded); })
      .catch(() => { if (!cancelled) setProjects([]); });
    return () => { cancelled = true; };
  }, []);

  return (
    <select
      aria-label={ariaLabel}
      value={value === null ? "" : String(value)}
      onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
      disabled={disabled || projects === null}
      className="h-8 max-w-40 rounded-md border border-input bg-background px-2 text-xs"
    >
      <option value="">No project</option>
      {(projects ?? []).map((project) => (
        <option key={project.id} value={project.id}>{project.name}</option>
      ))}
    </select>
  );
}
