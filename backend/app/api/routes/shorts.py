"""Shorts REST API: generate highlight clips and list/download them."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import OUTPUTS_DIR
from app.models.processing_job import ProcessingJob
from app.models.short_clip import ShortClip
from app.models.video import Video
from app.repositories.videos import get_owned_video
from app.schemas.job import ProcessingJobResponse
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/shorts", tags=["shorts"])


class GenerateShortsRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=10)
    clip_duration: float = Field(default=30.0, ge=5.0, le=180.0)
    aspect_ratio: str = Field(default="9:16", pattern=r"^(9:16|1:1|4:5)$")
    burn_subtitles: str | None = Field(default="srt", pattern=r"^(ass|srt)$")
    subtitle_source: str = Field(default="transcript", pattern=r"^(transcript|translation)$")
    language: str | None = Field(default=None, min_length=2, max_length=16)


class ShortClipResponse(BaseModel):
    id: int
    video_id: int
    job_id: int
    start_time: float
    end_time: float
    score: float
    duration: float

    model_config = {"from_attributes": True}


@router.post("/generate/{video_id}", response_model=ProcessingJobResponse,
             status_code=status.HTTP_201_CREATED)
async def generate_shorts(video_id: int, payload: GenerateShortsRequest,
                          current_user: CurrentUser, db: DbSession):
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    params = payload.model_dump()
    return await queue_processing_job(db, video.id, "shorts", params=params)


@router.get("/video/{video_id}", response_model=list[ShortClipResponse])
def list_shorts(video_id: int, current_user: CurrentUser, db: DbSession):
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    clips = db.scalars(
        select(ShortClip).where(ShortClip.video_id == video.id).order_by(ShortClip.start_time)
    ).all()
    return [ShortClipResponse(id=c.id, video_id=c.video_id, job_id=c.job_id,
                              start_time=c.start_time, end_time=c.end_time,
                              score=c.score, duration=c.end_time - c.start_time)
            for c in clips]


@router.get("/{clip_id}/download")
def download_short(clip_id: int, current_user: CurrentUser, db: DbSession):
    clip = db.scalar(
        select(ShortClip).join(Video, ShortClip.video_id == Video.id)
        .where(ShortClip.id == clip_id, Video.user_id == current_user.id)
    )
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    path = OUTPUTS_DIR / clip.output_path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip file not found")
    return FileResponse(path, media_type="video/mp4",
                        filename=f"short_{clip.id}_{int(clip.start_time)}s.mp4")
