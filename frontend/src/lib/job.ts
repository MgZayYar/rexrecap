export type ProcessingJob = {
  id: number;
  video_id: number;
  job_type: "transcription" | "translation" | "dubbing" | "autocrop" | "face_detection" | "subtitle_burn" | "render";
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  has_output: boolean;
};

export function estimatedState(job: ProcessingJob | null): string {
  if (!job) return "Not started";
  if (job.status === "queued") return "Waiting for worker";
  if (job.status === "processing") return `Processing ${job.job_type}`;
  if (job.status === "completed") return "Ready";
  return "Needs attention";
}
