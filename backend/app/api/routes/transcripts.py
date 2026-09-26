from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.transcript import Transcript
from app.models.video import Video
from app.repositories.videos import get_owned_video
from app.schemas.job import ProcessingJobResponse
from app.schemas.transcript import TranscriptResponse
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.post("/start/{video_id}", response_model=ProcessingJobResponse, status_code=status.HTTP_201_CREATED)
async def start_transcription(video_id: int, current_user: CurrentUser, db: DbSession) -> ProcessingJobResponse:
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return await queue_processing_job(db, video.id, "transcription")


@router.get("/{video_id}", response_model=TranscriptResponse)
def get_transcript(video_id: int, current_user: CurrentUser, db: DbSession) -> Transcript:
    transcript = db.scalar(
        select(Transcript).join(Video).where(Transcript.video_id == video_id, Video.user_id == current_user.id)
    )
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")
    return transcript
