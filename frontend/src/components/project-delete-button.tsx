"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { apiDelete, toMessage } from "@/lib/api-client";

/** Deleting a project keeps its videos — they become unassigned. */
export function ProjectDeleteButton({ projectId, projectName }: { projectId: number; projectName: string }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    if (!window.confirm(`Delete project "${projectName}"? Its videos will be kept as unassigned.`)) return;
    setDeleting(true);
    setError(null);
    try {
      await apiDelete(`/api/projects/${projectId}`);
      router.refresh();
    } catch (err) {
      setError(toMessage(err, "Could not delete the project."));
      setDeleting(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <Button variant="outline" size="sm" type="button" onClick={() => void remove()} disabled={deleting}>
        {deleting ? "Deleting…" : "Delete"}
      </Button>
      {error && <span className="text-xs text-red-600" role="alert">{error}</span>}
    </span>
  );
}
