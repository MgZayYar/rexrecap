"""Shorts worker: detect highlight moments and cut vertical clips.

For each detected window the worker:
1. cuts the window out of the source video,
2. smart-crops it to the requested vertical aspect ratio (face-tracked),
3. optionally burns subtitles (shifted to the clip's timeline),
4. stores the MP4 in storage/outputs and persists a ShortClip row.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import FFMPEG_BINARY, OUTPUTS_DIR, UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.short_clip import ShortClip
from app.models.video import Video
from app.services.subtitles import resolve_subtitle_segments
from app.video.subtitles import segments_to_ass, segments_to_srt
from app.video.analyze import probe_video
from app.video.ffmpeg import run_ffmpeg
from app.video.highlights import find_highlight_windows
from app.video.reframe import crop_size_for_ratio, render_crop_async
from app.video.smartcrop import plan_crop_trajectory
from app.video.subtitles import burn_subtitles
from app.workers.jobs.simulation import ProgressReporter

logger = logging.getLogger("rexcrop.shorts")


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for shorts job was not found")
        params = dict(job.params or {})
        count = max(1, min(int(params.get("count", 3)), 10))
        clip_duration = max(5.0, min(float(params.get("clip_duration", 30.0)), 180.0))
        aspect_ratio = params.get("aspect_ratio", "9:16")
        burn_format = params.get("burn_subtitles")
        subtitle_source = str(params.get("subtitle_source", "transcript"))
        language = params.get("language")
        segments = resolve_subtitle_segments(db, video.id, subtitle_source, language)
        video_id = video.id
        video_path = UPLOADS_DIR / video.stored_filename

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")
    if burn_format is not None and burn_format not in ("ass", "srt"):
        raise RuntimeError(f"Unsupported subtitle format: {burn_format!r}")

    await report_progress(3)
    windows = await asyncio.to_thread(
        find_highlight_windows, video_path, segments,
        count, clip_duration)
    if not windows:
        raise RuntimeError("Could not detect any highlight windows")
    await report_progress(8)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    made: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="rexcrop-shorts-") as tmp:
        tmpdir = Path(tmp)
        for i, window in enumerate(windows):
            start, end = window["start"], window["end"]
            await report_progress(8 + int(88 * i / len(windows)))

            cut_path = tmpdir / f"cut{i}.mp4"
            await asyncio.to_thread(
                run_ffmpeg,
                "-y", "-v", "error",
                "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
                "-i", str(video_path),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", str(cut_path))

            info = await asyncio.to_thread(probe_video, cut_path)
            crop_w, crop_h = crop_size_for_ratio(info.width, info.height, aspect_ratio)
            trajectory = await plan_crop_trajectory(cut_path, info, crop_w, None)
            vertical_path = tmpdir / f"vertical{i}.mp4"
            await render_crop_async(
                cut_path, vertical_path, trajectory, (crop_w, crop_h),
                info.duration or (end - start))

            final_path = vertical_path
            if burn_format and segments:
                shifted = [{"start": max(float(s["start"]) - start, 0.0),
                            "end": max(float(s["end"]) - start, 0.0),
                            "text": s["text"]}
                           for s in segments
                           if float(s["end"]) > start and float(s["start"]) < end]
                if shifted:
                    text = segments_to_ass(shifted) if burn_format == "ass" else segments_to_srt(shifted)
                    burned_path = tmpdir / f"burned{i}.mp4"
                    await asyncio.to_thread(
                        burn_subtitles, vertical_path, burned_path, text, burn_format)
                    final_path = burned_path

            filename = f"{uuid.uuid4().hex}_short{i}.mp4"
            await asyncio.to_thread(_move, final_path, OUTPUTS_DIR / filename)
            made.append({"start_time": start, "end_time": end, "score": window["score"],
                         "output_path": filename})

    with SessionLocal() as db:
        for clip in made:
            db.add(ShortClip(video_id=video_id, job_id=job_id, **clip))
        job = db.get(ProcessingJob, job_id)
        if job is not None and made:
            job.output_path = made[0]["output_path"]
        db.commit()
    _sync_clips_to_remote(job_id, [c["output_path"] for c in made])
    await report_progress(100)


def _sync_clips_to_remote(job_id: int, filenames: list[str]) -> None:
    """Upload finished clips to object storage when configured.

    Failures are logged only; local files remain the source of truth.
    """
    from app.storage import get_storage_backend, is_remote_delivery, remote_key_for_output

    if not is_remote_delivery():
        return
    backend = get_storage_backend()
    synced: dict[str, str] = {}
    for filename in filenames:
        local_path = OUTPUTS_DIR / filename
        if not local_path.is_file():
            continue
        key = remote_key_for_output(filename)
        try:
            backend.put_file(key, local_path, content_type="video/mp4")
            synced[filename] = key
        except Exception:
            logger.exception("shorts job %s: remote sync of %s failed", job_id, key)
    if not synced:
        return
    with SessionLocal() as db:
        clips = db.scalars(select(ShortClip).where(ShortClip.job_id == job_id)).all()
        for clip in clips:
            if clip.output_path in synced:
                clip.remote_key = synced[clip.output_path]
        db.commit()


def _move(src: Path, dst: Path) -> None:
    shutil.move(str(src), str(dst))
