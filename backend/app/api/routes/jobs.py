from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.repositories.videos import get_owned_video
from app.schemas.job import CreateJobRequest, ProcessingJobResponse
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/jobs", tags=["processing jobs"])


def get_owned_job(job_id: int, current_user: CurrentUser, db: DbSession) -> ProcessingJob:
    job = db.scalar(
        select(ProcessingJob).join(Video).where(ProcessingJob.id == job_id, Video.user_id == current_user.id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing job not found")
    return job


@router.post("/create", response_model=ProcessingJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(payload: CreateJobRequest, current_user: CurrentUser, db: DbSession) -> ProcessingJob:
    if payload.job_type == "translation":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use the translations endpoint and choose a target language")
    video = get_owned_video(db, payload.video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return await queue_processing_job(db, video.id, payload.job_type)


@router.get("/video/{video_id}", response_model=list[ProcessingJobResponse])
def list_video_jobs(video_id: int, current_user: CurrentUser, db: DbSession) -> list[ProcessingJob]:
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return list(db.scalars(select(ProcessingJob).where(ProcessingJob.video_id == video.id).order_by(ProcessingJob.created_at.desc())))


@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_job(job_id: int, current_user: CurrentUser, db: DbSession) -> ProcessingJob:
    return get_owned_job(job_id, current_user, db)
