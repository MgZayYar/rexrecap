"""Dubbing audio engine.

Turns timestamped segments into a dubbed video: assigns speaker turns from
pauses, synthesizes each segment with the speaker's voice, places every dub
at its original timestamp, and mixes it over the original audio ducked to a
low bed (this preserves music/ambience without stem separation).

Limitations (v1): TTS that runs longer than its segment overlaps the next
one instead of being time-stretched; speaker turns come from pause gaps,
not neural diarization.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from app.ai.dubbing.providers import TTSProvider, Voice
from app.video.ffmpeg import run_ffmpeg

BACKGROUND_VOLUME = 0.15
_SYNTH_CONCURRENCY = 4


def assign_speakers(segments: list[dict], gap_threshold: float = 1.5) -> list[tuple[dict, str]]:
    """Group segments into speaker turns: a pause longer than `gap_threshold`
    seconds starts a new turn, alternating speakers 'A' and 'B'."""
    assigned: list[tuple[dict, str]] = []
    speaker = "A"
    previous_end: float | None = None
    for segment in segments:
        start = float(segment.get("start", 0))
        if previous_end is not None and start - previous_end > gap_threshold:
            speaker = "B" if speaker == "A" else "A"
        assigned.append((segment, speaker))
        previous_end = float(segment.get("end", start))
    return assigned


async def synthesize_segments(
    provider: TTSProvider,
    assigned: list[tuple[dict, str]],
    voices: dict[str, Voice],
    workdir: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[tuple[dict, Path]]:
    """TTS every non-empty segment; returns [(segment, mp3_path)]."""
    speakable = [(seg, spk) for seg, spk in assigned if str(seg.get("text", "")).strip()]
    if not speakable:
        raise RuntimeError("No speakable segments found for dubbing")

    workdir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(_SYNTH_CONCURRENCY)
    done = 0

    async def _one(index: int, segment: dict, speaker: str) -> tuple[dict, Path]:
        nonlocal done
        async with semaphore:
            path = workdir / f"dub-{index:04d}.mp3"
            await provider.synthesize(str(segment["text"]).strip(), voices[speaker].id, path)
            done += 1
            if on_progress:
                on_progress(done, len(speakable))
            return segment, path

    results = await asyncio.gather(*(_one(i, seg, spk) for i, (seg, spk) in enumerate(speakable)))
    return list(results)


def build_dubbed_video(
    video_path: Path,
    dubbed: list[tuple[dict, Path]],
    output_path: Path,
    background_volume: float = BACKGROUND_VOLUME,
) -> None:
    """Mix timed dubs over ducked original audio; video stream is copied."""
    if not dubbed:
        raise RuntimeError("Nothing to mix: no dubbed segments")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filters: list[str] = []
    for i, (segment, _path) in enumerate(dubbed):
        delay_ms = int(float(segment.get("start", 0)) * 1000)
        filters.append(
            f"[{i + 1}:a]aformat=sample_rates=44100:channel_layouts=mono,"
            f"adelay={delay_ms}[d{i}]"
        )
    dub_inputs = "".join(f"[d{i}]" for i in range(len(dubbed)))
    filters.append(f"{dub_inputs}amix=inputs={len(dubbed)}:normalize=0[dub]")
    filters.append(
        "[0:a]aformat=sample_rates=44100:channel_layouts=mono,"
        f"volume={background_volume}[bg]"
    )
    filters.append("[dub][bg]amix=inputs=2:normalize=0[aout]")

    args = ["-y", "-i", str(video_path)]
    args.extend(arg for _, path in dubbed for arg in ("-i", str(path)))
    args.extend([
        "-filter_complex", ";".join(filters),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ])
    run_ffmpeg(*args, timeout=1800)
