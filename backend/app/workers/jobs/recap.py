"""Recap assistant worker: generate a structured recap draft from the transcript.

Requires a completed transcript on the video and OPENAI_API_KEY in the
environment. The draft (titles, hook, beats, key quotes) is persisted as a
RecapDraft row for the UI to render.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import RECAP_MODEL
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.recap_draft import RecapDraft
from app.models.transcript import Transcript
from app.models.video import Video
from app.services.recap_assistant import generate_recap_draft
from app.workers.jobs.simulation import ProgressReporter

logger = logging.getLogger("rexcrop.recap")


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for recap job was not found")
        video_id = video.id
        # Transcript is keyed by video_id (unique), not by its own id.
        from sqlalchemy import select
        transcript = db.scalar(select(Transcript).where(Transcript.video_id == video_id))
        if transcript is None or not transcript.segments:
            raise RuntimeError("This video has no transcript yet — transcribe it first")
        segments = list(transcript.segments)

    await report_progress(10)
    content = await asyncio.to_thread(generate_recap_draft, segments)
    await report_progress(90)

    with SessionLocal() as db:
        db.add(RecapDraft(video_id=video_id, job_id=job_id, content=content,
                          model=RECAP_MODEL))
        db.commit()
    logger.info("job %s: recap draft with %d beats", job_id, len(content.get("beats", [])))
    await report_progress(100)
