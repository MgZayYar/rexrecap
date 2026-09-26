"""Subtitle file generation and burn-in.

Builds SRT/ASS subtitle documents from transcript-style segments
(`[{start, end, text}]`) and burns them into a video with FFmpeg's libass
filters (`subtitles` for SRT, `ass` for ASS). The ASS output uses a clean
recap style: bold white text with a dark outline, bottom-center.
"""

from __future__ import annotations

from pathlib import Path

from app.video.ffmpeg import run_ffmpeg

ASS_STYLE_NAME = "RexCrop"


def _srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _ass_timestamp(seconds: float) -> str:
    total_cs = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(total_cs, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def segments_to_srt(segments: list[dict]) -> str:
    """Render segments as an SRT document."""
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = _srt_timestamp(float(segment["start"]))
        end = _srt_timestamp(float(segment["end"]))
        text = str(segment["text"]).strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _ass_escape(text: str) -> str:
    return str(text).strip().replace("\n", "\\N")


def segments_to_ass(segments: list[dict], play_res_x: int = 1280,
                    play_res_y: int = 720) -> str:
    """Render segments as an ASS document with the RexCrop recap style."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {ASS_STYLE_NAME},Noto Sans,52,&H00FFFFFF,&H000019FF,&H80000000,&H80000000,-1,0,0,0,100,100,0,0,1,2.5,0,2,20,20,28,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for segment in segments:
        start = _ass_timestamp(float(segment["start"]))
        end = _ass_timestamp(float(segment["end"]))
        events.append(
            f"Dialogue: 0,{start},{end},{ASS_STYLE_NAME},,0,0,0,,{_ass_escape(segment['text'])}"
        )
    return header + "\n".join(events) + ("\n" if events else "")


def _escape_filter_path(path: Path) -> str:
    """Escape a file path for use inside an FFmpeg filter argument."""
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def burn_subtitles(input_path: Path, output_path: Path, subtitle_text: str,
                   subtitle_format: str = "ass") -> None:
    """Burn `subtitle_text` into the video, writing `output_path`.

    `subtitle_format` is "srt" or "ass". Video is re-encoded (libx264);
    audio is copied untouched.
    """
    if subtitle_format not in ("srt", "ass"):
        raise ValueError(f"Unsupported subtitle format: {subtitle_format!r}")
    if not subtitle_text.strip():
        raise ValueError("Cannot burn empty subtitles")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = ".ass" if subtitle_format == "ass" else ".srt"
    # Write beside the output so the temp file shares the filesystem.
    subtitle_path = output_path.with_suffix(f".burn{suffix}")
    try:
        subtitle_path.write_text(subtitle_text, encoding="utf-8")
        escaped = _escape_filter_path(subtitle_path)
        if subtitle_format == "ass":
            video_filter = f"ass={escaped}"
        else:
            video_filter = (
                "subtitles=" + escaped +
                ":force_style='FontName=Noto Sans,FontSize=22,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=24'"
            )
        run_ffmpeg(
            "-y",
            "-i", str(input_path),
            "-vf", video_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
            timeout=600,
        )
    finally:
        subtitle_path.unlink(missing_ok=True)
