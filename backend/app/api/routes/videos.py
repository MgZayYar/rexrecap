from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import UPLOADS_DIR
from app.models.video import Video
from app.schemas.video import VideoResponse

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/x-matroska", "video/x-msvideo"}


def get_owned_video(video_id: int, current_user: CurrentUser, db: DbSession) -> Video:
    video = db.scalar(select(Video).where(Video.id == video_id, Video.user_id == current_user.id))
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> Video:
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
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video
    except HTTPException:
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
    video = get_owned_video(video_id, current_user, db)
    path = UPLOADS_DIR / video.stored_filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")
    return FileResponse(path, media_type=video.content_type, filename=video.filename)


@router.get("/{video_id}/playback")
def playback_video(video_id: int, current_user: CurrentUser, db: DbSession) -> FileResponse:
    video = get_owned_video(video_id, current_user, db)
    path = UPLOADS_DIR / video.stored_filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")
    return FileResponse(path, media_type=video.content_type, content_disposition_type="inline")
