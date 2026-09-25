import asyncio

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.translation import Translation
from app.services.translation import translate_segment_batch
from app.workers.jobs.simulation import ProgressReporter

SEGMENTS_PER_BATCH = 50


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        translation = db.scalar(select(Translation).where(Translation.job_id == job_id))
        if translation is None:
            raise RuntimeError("Translation details were not found")
        transcript = db.get(Transcript, translation.transcript_id)
        if transcript is None:
            raise RuntimeError("Source transcript was not found")
        source_language = transcript.language
        target_language = translation.target_language_name
        source_segments = list(transcript.segments)

    if not source_segments:
        raise RuntimeError("Source transcript has no timestamped segments")

    translated_segments: list[dict[str, object]] = []
    batches = [source_segments[index:index + SEGMENTS_PER_BATCH] for index in range(0, len(source_segments), SEGMENTS_PER_BATCH)]
    for batch_index, batch in enumerate(batches):
        translated_texts = await asyncio.to_thread(translate_segment_batch, source_language, target_language, batch)
        translated_segments.extend(
            {"start": segment["start"], "end": segment["end"], "text": text}
            for segment, text in zip(batch, translated_texts, strict=True)
        )
        await report_progress(10 + int(80 * (batch_index + 1) / len(batches)))

    with SessionLocal() as db:
        translation = db.scalar(select(Translation).where(Translation.job_id == job_id))
        if translation is None:
            raise RuntimeError("Translation details were not found")
        translation.segments = translated_segments
        translation.full_text = " ".join(str(segment["text"]) for segment in translated_segments)
        db.commit()
    await report_progress(95)
