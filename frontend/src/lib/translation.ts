import type { TranscriptSegment } from "@/lib/transcript";

export type Translation = {
  id: number;
  transcript_id: number;
  target_language: string;
  target_language_name: string;
  full_text: string | null;
  segments: TranscriptSegment[] | null;
  created_at: string;
  updated_at: string;
};
