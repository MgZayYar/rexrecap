"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { apiPost, toMessage } from "@/lib/api-client";
import type { Project } from "@/lib/video";

export function ProjectCreateForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (name.trim() === "" || saving) return;
    setSaving(true);
    setError(null);
    try {
      await apiPost<Project>("/api/projects", {
        name: name.trim(),
        description: description.trim() === "" ? null : description.trim(),
      });
      setName("");
      setDescription("");
      router.refresh();
    } catch (err) {
      setError(toMessage(err, "Could not create the project."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="font-medium">New project</h2>
      <div className="mt-3 grid gap-3">
        <input
          aria-label="Project name"
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          placeholder="Project name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={120}
        />
        <input
          aria-label="Project description"
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          placeholder="Description (optional)"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600" role="alert">{error}</p>}
      <Button className="mt-3" type="submit" disabled={saving || name.trim() === ""}>
        {saving ? "Creating…" : "Create project"}
      </Button>
    </form>
  );
}
