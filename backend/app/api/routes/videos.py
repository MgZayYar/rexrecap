from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import MAX_UPLOAD_BYTES, UPLOADS_DIR
from app.models.video import Video
from app.repositories.projects import get_owned_project
from app.repositories.videos import get_owned_video
from app.schemas.video import VideoResponse, VideoUpdate

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/x-matroska", "video/x-msvideo"}


def require_owned_video(video_id: int, current_user: CurrentUser, db: DbSession) -> Video:
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    project_id: int | None = Form(None),
) -> Video:
    if project_id is not None and get_owned_project(db, project_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    original_filename = Path(file.filename or "upload").name
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only mp4, mov, mkv, and avi files are allowed")
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported video content type")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{extension}"
    destination = UPLOADS_DIR / stored_filename
    size_bytes = 0

    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Video exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit",
                    )
                output.write(chunk)
        if size_bytes == 0:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

        video = Video(
            user_id=current_user.id,
            filename=original_filename,
            stored_filename=stored_filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=size_bytes,
            status="uploaded",
            project_id=project_id,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to save video") from exc
    finally:
        await file.close()


@router.get("", response_model=list[VideoResponse])
def list_videos(current_user: CurrentUser, db: DbSession) -> list[Video]:
    return list(db.scalars(select(Video).where(Video.user_id == current_user.id).order_by(Video.created_at.desc())))


@router.get("/{video_id}/download")
def download_video(video_id: int, current_user: CurrentUser, db: DbSession) -> FileResponse:
    video = require_owned_video(video_id, current_user, db)
    path = UPLOADS_DIR / video.stored_filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")
    return FileResponse(path, media_type=video.content_type, filename=video.filename)


@router.get("/{video_id}/playback")
def playback_video(video_id: int, current_user: CurrentUser, db: DbSession) -> FileResponse:
    video = require_owned_video(video_id, current_user, db)
    path = UPLOADS_DIR / video.stored_filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")
    return FileResponse(path, media_type=video.content_type, content_disposition_type="inline")


@router.patch("/{video_id}", response_model=VideoResponse)
def update_video(video_id: int, payload: VideoUpdate, current_user: CurrentUser, db: DbSession) -> Video:
    video = require_owned_video(video_id, current_user, db)
    if "project_id" in payload.model_fields_set:
        if payload.project_id is not None and get_owned_project(db, payload.project_id, current_user.id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        video.project_id = payload.project_id
    db.commit()
    db.refresh(video)
    return video
