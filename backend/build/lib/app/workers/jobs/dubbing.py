"""Real dubbing worker.

Pipeline: load job + video + transcript (or translation for the target
language) -> detect speaker turns from pauses -> resolve per-speaker voices
-> synthesize every segment -> mix dubs over ducked original audio and mux
with the video -> record the output file on the job.
"""

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.ai.dubbing.audio import assign_speakers, build_dubbed_video, synthesize_segments
from app.ai.dubbing.providers import get_provider
from app.ai.dubbing.voices import resolve_speaker_voices
from app.core.config import OUTPUTS_DIR, UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.translation import Translation
from app.models.video import Video
from app.workers.jobs.simulation import ProgressReporter


def _segments_for_job(db, job: ProcessingJob) -> tuple[list[dict], str]:
    """Transcript segments, or the translation's when a target language was requested."""
    transcript = db.scalar(select(Transcript).where(Transcript.video_id == job.video_id))
    if transcript is None:
        raise RuntimeError("Transcribe the video before dubbing it")
    params = job.params or {}
    target_language = params.get("target_language")
    if target_language:
        translation = db.scalar(
            select(Translation)
            .join(Transcript, Translation.transcript_id == Transcript.id)
            .where(Transcript.video_id == job.video_id,
                   Translation.target_language == target_language)
        )
        if translation is None:
            raise RuntimeError(f"No {target_language} translation exists for this video")
        return list(translation.segments or []), target_language
    return list(transcript.segments or []), transcript.language or "en"


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for dubbing job was not found")
        segments, language = _segments_for_job(db, job)
        params = dict(job.params or {})
        video_path = UPLOADS_DIR / video.stored_filename

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")
    if not segments:
        raise RuntimeError("The transcript has no segments to dub")

    await report_progress(5)
    provider_name = params.get("provider") or "edge"
    provider = get_provider(provider_name)
    assigned = assign_speakers(segments, gap_threshold=float(params.get("gap_threshold", 1.5)))
    voices = await resolve_speaker_voices(provider_name, language, params.get("voice"))
    await report_progress(10)

    loop = asyncio.get_running_loop()

    def _on_synth(done: int, total: int) -> None:
        # synthesize_segments awaits on the event loop, so this runs on-loop.
        progress = 10 + int(45 * done / max(total, 1))
        loop.create_task(report_progress(progress))

    filename = f"{uuid4().hex}_dubbed.mp4"
    output_path = OUTPUTS_DIR / filename
    with tempfile.TemporaryDirectory(prefix="rexcrop-dub-") as tmp:
        dubbed = await synthesize_segments(provider, assigned, voices, Path(tmp), _on_synth)
        await report_progress(58)
        await asyncio.to_thread(build_dubbed_video, video_path, dubbed, output_path)
        await report_progress(90)

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            raise RuntimeError("Dubbing job was not found")
        job.output_path = filename
        db.commit()
    await report_progress(95)
