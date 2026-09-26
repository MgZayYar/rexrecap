"""Subtitle burn worker.

Pipeline: load job + video -> read the transcript (or a translation) ->
render an SRT/ASS document -> burn it into the video with FFmpeg/libass ->
record the output file on the job. Video is re-encoded; audio is copied.
"""

import asyncio
from uuid import uuid4

from app.core.config import OUTPUTS_DIR, UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.services.subtitles import resolve_subtitle_segments
from app.video.subtitles import burn_subtitles, segments_to_ass, segments_to_srt
from app.workers.jobs.simulation import ProgressReporter


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for subtitle burn job was not found")
        params = dict(job.params or {})
        source = str(params.get("source", "transcript"))
        subtitle_format = str(params.get("format", "ass"))
        language = params.get("language")
        video_id = video.id
        video_path = UPLOADS_DIR / video.stored_filename
        segments = resolve_subtitle_segments(db, video_id, source, language)

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")
    if not segments:
        raise RuntimeError(
            "No transcript available for subtitle burn" if source == "transcript"
            else "No translation available for subtitle burn"
        )

    await report_progress(10)
    subtitle_text = (
        segments_to_ass(segments) if subtitle_format == "ass" else segments_to_srt(segments)
    )
    filename = f"{uuid4().hex}_subtitled.mp4"
    output_path = OUTPUTS_DIR / filename

    await asyncio.to_thread(burn_subtitles, video_path, output_path, subtitle_text,
                            subtitle_format)
    await report_progress(90)

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            raise RuntimeError("Subtitle burn job was not found")
        job.output_path = filename
        db.commit()
    await report_progress(95)
