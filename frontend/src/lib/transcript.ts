export type TranscriptSegment = { start: number; end: number; text: string };

export type Transcript = {
  id: number;
  video_id: number;
  language: string;
  full_text: string;
  segments: TranscriptSegment[];
  created_at: string;
};

export function formatTimestamp(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`;
}
