export type ProcessingJob = {
  id: number;
  video_id: number;
  job_type:
    | "transcription"
    | "translation"
    | "dubbing"
    | "autocrop"
    | "face_detection"
    | "subtitle_burn"
    | "render"
    | "shorts"
    | "thumbnails"
    | "recap";
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  progress: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  has_output: boolean;
  cancel_requested: boolean;
};

export type WorkerInfo = {
  worker_id: string;
  started_at: string;
  last_seen: string;
  current_job_id: number | null;
  is_live: boolean;
};

export function estimatedState(job: ProcessingJob | null): string {
  if (!job) return "Not started";
  if (job.status === "queued") return "Waiting for worker";
  if (job.status === "processing") return job.cancel_requested ? "Cancelling…" : `Processing ${job.job_type}`;
  if (job.status === "completed") return "Ready";
  if (job.status === "cancelled") return "Cancelled";
  return "Needs attention";
}

export function isTerminalStatus(status: ProcessingJob["status"]): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}
