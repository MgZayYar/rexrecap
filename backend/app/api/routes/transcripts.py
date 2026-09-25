from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.video import Video
from app.schemas.job import ProcessingJobResponse
from app.schemas.transcript import TranscriptResponse
from app.workers.queue import job_queue

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.post("/start/{video_id}", response_model=ProcessingJobResponse, status_code=status.HTTP_201_CREATED)
async def start_transcription(video_id: int, current_user: CurrentUser, db: DbSession) -> ProcessingJob:
    video = db.scalar(select(Video).where(Video.id == video_id, Video.user_id == current_user.id))
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    job = ProcessingJob(video_id=video.id, job_type="transcription", status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    await job_queue.enqueue(job.id)
    return job


@router.get("/{video_id}", response_model=TranscriptResponse)
def get_transcript(video_id: int, current_user: CurrentUser, db: DbSession) -> Transcript:
    transcript = db.scalar(
        select(Transcript).join(Video).where(Transcript.video_id == video_id, Video.user_id == current_user.id)
    )
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")
    return transcript
