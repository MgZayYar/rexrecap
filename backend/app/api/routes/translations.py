from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.translation import Translation
from app.models.video import Video
from app.schemas.translation import CreateTranslationRequest, TranslationJobResponse, TranslationResponse
from app.services.languages import get_language_name
from app.workers.queue import job_queue

router = APIRouter(prefix="/translations", tags=["translations"])


@router.post("", response_model=TranslationJobResponse, status_code=status.HTTP_201_CREATED)
async def start_translation(payload: CreateTranslationRequest, current_user: CurrentUser, db: DbSession) -> TranslationJobResponse:
    language = payload.target_language.strip().lower()
    try:
        language_name = get_language_name(language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported target language") from exc

    transcript = db.scalar(
        select(Transcript).join(Video).where(Transcript.video_id == payload.video_id, Video.user_id == current_user.id)
    )
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generate a transcript before starting translation")

    translation = db.scalar(
        select(Translation).where(Translation.transcript_id == transcript.id, Translation.target_language == language)
    )
    if translation is not None:
        job = db.get(ProcessingJob, translation.job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Translation job is unavailable")
        if job.status in {"queued", "processing"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Translation is already in progress")
        if job.status == "completed":
            return TranslationJobResponse(job=job, translation=translation)
        job.status = "queued"
        job.progress = 0
        job.error_message = None
        job.started_at = None
        job.finished_at = None
        db.commit()
        db.refresh(job)
        await job_queue.enqueue(job.id)
        return TranslationJobResponse(job=job, translation=translation)

    job = ProcessingJob(video_id=payload.video_id, job_type="translation", status="queued", progress=0)
    db.add(job)
    db.flush()
    translation = Translation(
        transcript_id=transcript.id,
        job_id=job.id,
        target_language=language,
        target_language_name=language_name,
    )
    db.add(translation)
    db.commit()
    db.refresh(job)
    db.refresh(translation)
    await job_queue.enqueue(job.id)
    return TranslationJobResponse(job=job, translation=translation)


@router.get("/video/{video_id}", response_model=TranslationResponse)
def get_translation(video_id: int, target_language: str, current_user: CurrentUser, db: DbSession) -> Translation:
    language = target_language.strip().lower()
    translation = db.scalar(
        select(Translation)
        .join(Transcript)
        .join(Video)
        .where(Video.id == video_id, Video.user_id == current_user.id, Translation.target_language == language)
    )
    if translation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation not found")
    return translation
