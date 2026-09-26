import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.video.ffmpeg import extract_audio
from app.ai.whisper.transcriber import transcribe_audio
from app.core.config import UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.video import Video
from app.workers.jobs.simulation import ProgressReporter


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for transcription job was not found")
        video_path = UPLOADS_DIR / video.stored_filename

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")

    await report_progress(10)
    with tempfile.TemporaryDirectory(prefix="rexcrop-whisper-") as directory:
        audio_path = Path(directory) / "audio.wav"
        await asyncio.to_thread(extract_audio, video_path, audio_path)
        await report_progress(30)
        result = await asyncio.to_thread(transcribe_audio, audio_path)
        await report_progress(80)

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            raise RuntimeError("Transcription job was not found")
        transcript = db.scalar(select(Transcript).where(Transcript.video_id == job.video_id))
        segments = [{"start": item.start, "end": item.end, "text": item.text} for item in result.segments]
        if transcript is None:
            transcript = Transcript(video_id=job.video_id, language=result.language, full_text=result.full_text, segments=segments)
            db.add(transcript)
        else:
            transcript.language = result.language
            transcript.full_text = result.full_text
            transcript.segments = segments
        db.commit()
    await report_progress(95)
