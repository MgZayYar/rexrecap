import type { TranscriptSegment } from "@/lib/transcript";

export type SubtitleCue = TranscriptSegment & { id: string };
export type SubtitleStyle = { fontFamily: string; fontSize: number; color: string; background: string; position: "bottom" | "middle" | "top" };

export const defaultSubtitleStyle: SubtitleStyle = { fontFamily: "Arial", fontSize: 28, color: "#ffffff", background: "#000000", position: "bottom" };

export function makeCues(segments: TranscriptSegment[]): SubtitleCue[] {
  return segments.map((segment, index) => ({ ...segment, id: `${segment.start}-${index}` }));
}

function pad(value: number, length = 2) { return Math.floor(value).toString().padStart(length, "0"); }

export function srtTime(seconds: number) {
  const milliseconds = Math.round(Math.max(0, seconds) * 1000);
  return `${pad(milliseconds / 3_600_000)}:${pad((milliseconds % 3_600_000) / 60_000)}:${pad((milliseconds % 60_000) / 1000)},${(milliseconds % 1000).toString().padStart(3, "0")}`;
}

export function toSrt(cues: SubtitleCue[]) {
  return cues.map((cue, index) => `${index + 1}\n${srtTime(cue.start)} --> ${srtTime(cue.end)}\n${cue.text.trim()}`).join("\n\n");
}

function assTime(seconds: number) {
  const centiseconds = Math.round(Math.max(0, seconds) * 100);
  return `${Math.floor(centiseconds / 360000)}:${pad((centiseconds % 360000) / 6000)}:${pad((centiseconds % 6000) / 100)}.${pad(centiseconds % 100)}`;
}

function assColor(hex: string) {
  const value = hex.replace("#", "").padEnd(6, "0");
  return `&H00${value.slice(4, 6)}${value.slice(2, 4)}${value.slice(0, 2)}`;
}

export function toAss(cues: SubtitleCue[], style: SubtitleStyle) {
  const alignment = style.position === "top" ? 8 : style.position === "middle" ? 5 : 2;
  const header = `[Script Info]\nTitle: RexCrop subtitles\nScriptType: v4.00+\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: RexCrop,${style.fontFamily},${style.fontSize},${assColor(style.color)},${assColor(style.color)},&H00000000,${assColor(style.background)},0,0,0,0,100,100,0,0,1,2,0,${alignment},40,40,34,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text`;
  const events = cues.map((cue) => `Dialogue: 0,${assTime(cue.start)},${assTime(cue.end)},RexCrop,,0,0,0,,${cue.text.replaceAll("\n", "\\N")}`);
  return `${header}\n${events.join("\n")}`;
}
