"""Thumbnail candidates API: generate, list, preview, and select."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import OUTPUTS_DIR
from app.models.thumbnail import Thumbnail
from app.repositories.videos import get_owned_video
from app.schemas.job import ProcessingJobResponse
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/thumbnails", tags=["thumbnails"])


class GenerateThumbnailsRequest(BaseModel):
    count: int = Field(default=8, ge=1, le=16)


class ThumbnailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    timestamp: float
    score: float
    width: int
    height: int
    selected: bool = False


def _thumbnail_response(thumbnail: Thumbnail, selected_path: str | None) -> ThumbnailResponse:
    response = ThumbnailResponse.model_validate(thumbnail)
    response.selected = thumbnail.path == selected_path
    return response


@router.post("/generate/{video_id}", response_model=ProcessingJobResponse,
             status_code=status.HTTP_201_CREATED)
async def generate_thumbnails(video_id: int, payload: GenerateThumbnailsRequest,
                              current_user: CurrentUser, db: DbSession):
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return await queue_processing_job(db, video.id, "thumbnails",
                                      params={"count": payload.count})


@router.get("/video/{video_id}", response_model=list[ThumbnailResponse])
def list_thumbnails(video_id: int, current_user: CurrentUser, db: DbSession):
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    thumbnails = db.scalars(
        select(Thumbnail).where(Thumbnail.video_id == video.id)
        .order_by(Thumbnail.score.desc())
    ).all()
    return [_thumbnail_response(t, video.thumbnail_path) for t in thumbnails]


def _owned_thumbnail(thumbnail_id: int, user_id: int, db: DbSession) -> Thumbnail:
    thumbnail = db.scalar(
        select(Thumbnail).join(Thumbnail.video).where(
            Thumbnail.id == thumbnail_id,
            Thumbnail.video.has(user_id=user_id))
    )
    if thumbnail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Thumbnail not found")
    return thumbnail


@router.get("/{thumbnail_id}/image")
def thumbnail_image(thumbnail_id: int, current_user: CurrentUser, db: DbSession):
    thumbnail = _owned_thumbnail(thumbnail_id, current_user.id, db)
    # path is a worker-generated relative path; resolve defensively anyway.
    path = (OUTPUTS_DIR / thumbnail.path).resolve()
    if OUTPUTS_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Thumbnail file not found")
    return FileResponse(path, media_type="image/jpeg",
                        filename=f"thumbnail-{thumbnail.id}.jpg")


@router.post("/{thumbnail_id}/select", response_model=ThumbnailResponse)
def select_thumbnail(thumbnail_id: int, current_user: CurrentUser, db: DbSession):
    thumbnail = _owned_thumbnail(thumbnail_id, current_user.id, db)
    video = get_owned_video(db, thumbnail.video_id, current_user.id)
    assert video is not None  # owned via the join above
    video.thumbnail_path = thumbnail.path
    db.commit()
    db.refresh(thumbnail)
    return _thumbnail_response(thumbnail, video.thumbnail_path)
