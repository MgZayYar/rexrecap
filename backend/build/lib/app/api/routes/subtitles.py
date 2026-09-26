"""Subtitle burn API: burn transcript/translation subtitles into the video."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.transcript import Transcript
from app.models.translation import Translation
from app.models.video import Video
from app.repositories.videos import get_owned_video
from app.schemas.job import ProcessingJobResponse
from app.schemas.subtitle import BurnSubtitlesRequest
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/subtitles", tags=["subtitles"])


@router.post("/burn/{video_id}", response_model=ProcessingJobResponse,
             status_code=status.HTTP_201_CREATED)
async def burn_subtitles(video_id: int, payload: BurnSubtitlesRequest,
                         current_user: CurrentUser, db: DbSession) -> ProcessingJobResponse:
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    transcript = db.scalar(select(Transcript).where(Transcript.video_id == video.id))
    if transcript is None or not transcript.segments:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Generate a transcript before burning subtitles")

    language = (payload.language or "").lower() or None
    if payload.source == "translation":
        if language is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="Choose a target language to burn translated subtitles")
        translation = db.scalar(
            select(Translation)
            .join(Transcript, Translation.transcript_id == Transcript.id)
            .where(Transcript.video_id == video.id,
                   Translation.target_language == language)
        )
        if translation is None or not translation.segments:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"No {language} translation exists for this video")

    params = {"source": payload.source, "format": payload.format, "language": language}
    return await queue_processing_job(db, video.id, "subtitle_burn", params=params)
