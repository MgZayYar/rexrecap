from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import OUTPUTS_DIR
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.models.worker_heartbeat import WorkerHeartbeat
from app.repositories.videos import get_owned_video
from app.storage import remote_download_url
from app.schemas.job import CreateJobRequest, JobStatus, ProcessingJobResponse, WorkerHeartbeatResponse
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
    return await queue_processing_job(db, video.id, payload.job_type, params=payload.params)


@router.get("/video/{video_id}", response_model=list[ProcessingJobResponse])
def list_video_jobs(video_id: int, current_user: CurrentUser, db: DbSession) -> list[ProcessingJob]:
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return list(db.scalars(select(ProcessingJob).where(ProcessingJob.video_id == video.id).order_by(ProcessingJob.created_at.desc())))


@router.get("", response_model=list[ProcessingJobResponse])
def list_jobs(
    current_user: CurrentUser,
    db: DbSession,
    status: JobStatus | None = Query(default=None),
    video_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ProcessingJob]:
    """List the current user's jobs, newest first, optionally filtered."""
    query = (
        select(ProcessingJob)
        .join(Video)
        .where(Video.user_id == current_user.id)
        .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
    )
    if status is not None:
        query = query.where(ProcessingJob.status == status)
    if video_id is not None:
        if get_owned_video(db, video_id, current_user.id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
        query = query.where(ProcessingJob.video_id == video_id)
    return list(db.scalars(query.limit(limit)))


@router.post("/{job_id}/cancel", response_model=ProcessingJobResponse)
def cancel_job(job_id: int, current_user: CurrentUser, db: DbSession) -> ProcessingJob:
    """Cancel a job.

    Queued jobs are cancelled immediately. A running job is asked to stop
    cooperatively: the worker aborts it at its next progress checkpoint.
    """
    job = get_owned_job(job_id, current_user, db)
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
    elif job.status == "processing":
        job.cancel_requested = True
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a job that is {job.status}")
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/retry", response_model=ProcessingJobResponse)
def retry_job(job_id: int, current_user: CurrentUser, db: DbSession) -> ProcessingJob:
    """Requeue a failed or cancelled job."""
    job = get_owned_job(job_id, current_user, db)
    if job.status not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot retry a job that is {job.status}")
    job.status = "queued"
    job.progress = 0
    job.error_message = None
    job.cancel_requested = False
    job.started_at = None
    job.finished_at = None
    db.commit()
    db.refresh(job)
    return job


@router.get("/workers", response_model=list[WorkerHeartbeatResponse])
def list_workers(current_user: CurrentUser, db: DbSession) -> list[WorkerHeartbeat]:
    """Worker processes that have checked in recently."""
    return list(db.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen.desc())))


@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_job(job_id: int, current_user: CurrentUser, db: DbSession) -> ProcessingJob:
    return get_owned_job(job_id, current_user, db)


@router.get("/{job_id}/output")
def download_job_output(job_id: int, current_user: CurrentUser, db: DbSession):
    job = get_owned_job(job_id, current_user, db)
    if not job.output_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This job has no output file")
    filename = f"rexcrop-{job.job_type}-{job.id}.mp4"
    remote_url = remote_download_url(job.output_remote_key, filename)
    if remote_url:
        return RedirectResponse(remote_url, status_code=status.HTTP_302_FOUND)
    # output_path is a worker-generated filename; resolve defensively anyway.
    path = (OUTPUTS_DIR / job.output_path).resolve()
    if OUTPUTS_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)
