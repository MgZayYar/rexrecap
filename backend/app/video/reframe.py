"""Smart reframing for several aspect ratios.

Computes a crop window for a target aspect ratio (9:16, 1:1, 4:5) and renders
it with FFmpeg. The crop window slides along a smoothed trajectory (see
app.video.analyze and app.video.smartcrop), so the subject stays in frame.
Rendering is chunked: each chunk is cropped with a fixed x offset, then
chunks are concatenated. Chunking keeps the FFmpeg invocation simple and
debuggable; the smoothed trajectory keeps motion natural.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.video.ffmpeg import run_ffmpeg

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "9:16": (9, 16),
    "1:1": (1, 1),
    "4:5": (4, 5),
}

OUTPUT_SLUGS = {"9:16": "916", "1:1": "11", "4:5": "45"}

# Backward-compatible default for the original vertical pipeline.
TARGET_RATIO = 9 / 16


def crop_size_for_ratio(frame_width: int, frame_height: int, ratio_name: str) -> tuple[int, int]:
    """Largest window of `ratio_name` that fits inside the frame (even dims)."""
    if ratio_name not in ASPECT_RATIOS:
        raise ValueError(f"Unsupported aspect ratio: {ratio_name!r} "
                         f"(expected one of {sorted(ASPECT_RATIOS)})")
    rw, rh = ASPECT_RATIOS[ratio_name]
    target = rw / rh
    crop_w = min(frame_width, round(frame_height * target))
    crop_h = min(frame_height, round(frame_width / target))
    # FFmpeg crop needs even dimensions for yuv420p.
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    return max(2, crop_w), max(2, crop_h)


def vertical_crop_size(frame_width: int, frame_height: int) -> tuple[int, int]:
    """Largest 9:16 window that fits inside the frame (even dimensions)."""
    return crop_size_for_ratio(frame_width, frame_height, "9:16")


def chunk_trajectory(trajectory: list[tuple[float, float]],
                     chunk_seconds: float) -> list[tuple[float, float, int]]:
    """Group (t, x) samples into chunks; each chunk uses the mean x, rounded.

    Returns [(chunk_start, chunk_end, crop_x)] covering the sampled range.
    """
    if not trajectory:
        return []
    chunks: list[tuple[float, float, int]] = []
    start_t = trajectory[0][0]
    bucket: list[float] = []
    for t, x in trajectory:
        if t - start_t >= chunk_seconds and bucket:
            chunks.append((start_t, t, round(sum(bucket) / len(bucket))))
            start_t = t
            bucket = []
        bucket.append(x)
    if bucket:
        end_t = trajectory[-1][0] + chunk_seconds
        chunks.append((start_t, end_t, round(sum(bucket) / len(bucket))))
    return chunks


def render_crop(input_path: Path, output_path: Path,
                trajectory: list[tuple[float, float]],
                crop_size: tuple[int, int],
                duration: float,
                chunk_seconds: float = 2.0,
                on_chunk: Callable[[int, int], None] | None = None) -> None:
    """Render the crop. `on_chunk(done, total)` reports progress."""
    crop_w, crop_h = crop_size
    chunks = chunk_trajectory(trajectory, chunk_seconds)
    if not chunks:
        # No trajectory (e.g. analysis found nothing): single centered crop.
        chunks = [(0.0, duration, 0)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rexcrop-reframe-") as tmp:
        tmpdir = Path(tmp)
        parts: list[Path] = []
        total = len(chunks)
        for i, (start, end, x) in enumerate(chunks):
            part = tmpdir / f"part-{i:04d}.mp4"
            length = max(0.1, end - start)
            run_ffmpeg(
                "-y",
                "-ss", f"{start:.3f}",
                "-t", f"{length:.3f}",
                "-i", str(input_path),
                "-vf", f"crop={crop_w}:{crop_h}:{x}:0",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                str(part),
                timeout=600,
            )
            parts.append(part)
            if on_chunk:
                on_chunk(i + 1, total)

        if len(parts) == 1:
            parts[0].replace(output_path)
            return
        filelist = tmpdir / "parts.txt"
        filelist.write_text("".join(f"file '{p}'\n" for p in parts))
        run_ffmpeg(
            "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(filelist),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_path),
            timeout=600,
        )


def render_vertical(input_path: Path, output_path: Path,
                    trajectory: list[tuple[float, float]],
                    crop_size: tuple[int, int],
                    duration: float,
                    chunk_seconds: float = 2.0,
                    on_chunk: Callable[[int, int], None] | None = None) -> None:
    """Render the 9:16 vertical crop (kept for backward compatibility)."""
    render_crop(input_path, output_path, trajectory, crop_size, duration,
                chunk_seconds=chunk_seconds, on_chunk=on_chunk)


async def render_crop_async(*args, **kwargs) -> None:
    """Async wrapper that runs the blocking render in a worker thread."""
    on_chunk = kwargs.pop("on_chunk", None)
    loop = asyncio.get_running_loop()

    def _report(done: int, total: int) -> None:
        if on_chunk:
            loop.call_soon_threadsafe(on_chunk, done, total)

    await asyncio.to_thread(render_crop, *args, **kwargs, on_chunk=_report)


async def render_vertical_async(*args, **kwargs) -> None:
    """Async wrapper for the 9:16 render (kept for backward compatibility)."""
    await render_crop_async(*args, **kwargs)
