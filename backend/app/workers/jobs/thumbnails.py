"""Thumbnails worker: extract and score thumbnail candidates.

For each candidate timestamp the worker:
1. extracts a JPEG frame with FFmpeg,
2. scores it by sharpness + face prominence,
3. stores it under storage/outputs/thumbnails and persists a Thumbnail row.

The best-scoring candidate is reported in the job result; the user picks the
final thumbnail in the UI (videos.thumbnail_path).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import OUTPUTS_DIR, UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.thumbnail import Thumbnail
from app.models.video import Video
from app.video.analyze import probe_video
from app.video.thumbnails import (
    ScoredFrame,
    extract_frame,
    pick_candidate_timestamps,
    score_candidates,
)
from app.workers.jobs.simulation import ProgressReporter

logger = logging.getLogger("rexcrop.thumbnails")

THUMBNAIL_DIR = OUTPUTS_DIR / "thumbnails"


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for thumbnails job was not found")
        params = dict(job.params or {})
        count = max(1, min(int(params.get("count", 8)), 16))
        video_id, stored_filename = video.id, video.stored_filename

    source = UPLOADS_DIR / stored_filename
    if not source.is_file():
        raise RuntimeError(f"Source video {stored_filename} is missing from uploads")

    info = await asyncio.to_thread(probe_video, source)
    timestamps = pick_candidate_timestamps(info.duration, count)
    if not timestamps:
        raise RuntimeError("Could not determine any thumbnail timestamps")

    frames: list[ScoredFrame] = []
    for index, timestamp in enumerate(timestamps):
        filename = f"{uuid.uuid4().hex}.jpg"
        output_path = THUMBNAIL_DIR / filename
        await asyncio.to_thread(extract_frame, source, timestamp, output_path)
        frames.append(ScoredFrame(path=output_path, timestamp=timestamp,
                                  width=0, height=0))
        await report_progress(int((index + 1) / len(timestamps) * 80))

    ranked = await asyncio.to_thread(score_candidates, frames)
    await report_progress(90)

    with SessionLocal() as db:
        for frame in ranked:
            db.add(Thumbnail(
                video_id=video_id,
                job_id=job_id,
                path=str(Path("thumbnails") / frame.path.name),
                timestamp=frame.timestamp,
                score=frame.score,
                width=frame.width,
                height=frame.height,
            ))
        db.commit()
        best = db.scalars(
            select(Thumbnail).where(Thumbnail.video_id == video_id,
                                   Thumbnail.job_id == job_id)
            .order_by(Thumbnail.score.desc())
        ).first()
        logger.info("job %s: %d thumbnails, best #%s (score %.3f)",
                    job_id, len(ranked), best.id if best else None,
                    best.score if best else 0.0)
    await report_progress(100)
