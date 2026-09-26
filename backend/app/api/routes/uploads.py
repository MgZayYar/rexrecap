"""Resumable chunked uploads.

Flow:
  POST   /videos/uploads              -> create a session (validates quota)
  GET    /videos/uploads/{id}         -> read the server-confirmed offset
  PATCH  /videos/uploads/{id}         -> append one chunk (Upload-Offset header
                                          must match the session's offset)
  POST   /videos/uploads/{id}/complete -> finalize into a Video
  DELETE /videos/uploads/{id}         -> abort and delete the partial file
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.api.routes.videos import ALLOWED_CONTENT_TYPES, ALLOWED_EXTENSIONS
from app.core.config import MAX_UPLOAD_BYTES, UPLOADS_DIR
from app.models.upload_session import UploadSession
from app.models.video import Video
from app.repositories.projects import get_owned_project
from app.schemas.upload import UploadSessionCreate, UploadSessionResponse
from app.schemas.video import VideoResponse
from app.services.storage import QuotaExceededError, check_quota

router = APIRouter(prefix="/videos/uploads", tags=["uploads"])


def _require_owned_session(upload_id: str, current_user: CurrentUser, db: DbSession) -> UploadSession:
    session = db.get(UploadSession, upload_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found")
    return session


def _validate_file(filename: str, content_type: str) -> tuple[str, str]:
    original = Path(filename).name
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only mp4, mov, mkv, and avi files are allowed")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported video content type")
    return original, extension


@router.post("", response_model=UploadSessionResponse, status_code=status.HTTP_201_CREATED)
def create_upload_session(
    payload: UploadSessionCreate, current_user: CurrentUser, db: DbSession
) -> UploadSession:
    original, _ = _validate_file(payload.filename, payload.content_type)
    if payload.total_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Video exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")
    project_id = payload.project_id
    if project_id is not None and get_owned_project(db, project_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    try:
        check_quota(db, current_user.id, payload.total_bytes)
    except QuotaExceededError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    temp_filename = f"{uuid4().hex}.part"
    (UPLOADS_DIR / temp_filename).touch()
    session = UploadSession(
        user_id=current_user.id,
        filename=original,
        temp_filename=temp_filename,
        content_type=payload.content_type,
        total_bytes=payload.total_bytes,
        project_id=project_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{upload_id}", response_model=UploadSessionResponse)
def get_upload_session(upload_id: str, current_user: CurrentUser, db: DbSession) -> UploadSession:
    return _require_owned_session(upload_id, current_user, db)


@router.patch("/{upload_id}", response_model=UploadSessionResponse)
async def append_chunk(
    upload_id: str, request: Request, current_user: CurrentUser, db: DbSession
) -> UploadSession:
    session = _require_owned_session(upload_id, current_user, db)
    if session.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Upload session is {session.status}")
    offset_header = request.headers.get("upload-offset")
    if offset_header is None or not offset_header.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Upload-Offset header with the byte offset is required")
    if int(offset_header) != session.received_bytes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Offset mismatch: server has {session.received_bytes} bytes")

    chunk = await request.body()
    if not chunk:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty chunk")
    if session.received_bytes + len(chunk) > session.total_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Chunk would exceed the declared total size")
    try:
        check_quota(db, current_user.id, len(chunk))
    except QuotaExceededError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc

    temp_path = UPLOADS_DIR / session.temp_filename
    try:
        with temp_path.open("ab") as output:
            output.write(chunk)
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Unable to write upload chunk") from exc
    session.received_bytes += len(chunk)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{upload_id}/complete", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def complete_upload(upload_id: str, current_user: CurrentUser, db: DbSession) -> Video:
    session = _require_owned_session(upload_id, current_user, db)
    if session.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Upload session is {session.status}")
    if session.received_bytes != session.total_bytes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Upload incomplete: {session.received_bytes} of {session.total_bytes} bytes received")

    temp_path = UPLOADS_DIR / session.temp_filename
    if not temp_path.is_file() or temp_path.stat().st_size != session.total_bytes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Uploaded file is incomplete or missing")

    extension = Path(session.filename).suffix.lower()
    stored_filename = f"{uuid4().hex}{extension}"
    temp_path.rename(UPLOADS_DIR / stored_filename)
    video = Video(
        user_id=current_user.id,
        filename=session.filename,
        stored_filename=stored_filename,
        content_type=session.content_type,
        size_bytes=session.total_bytes,
        status="uploaded",
        project_id=session.project_id,
    )
    session.status = "completed"
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def abort_upload(upload_id: str, current_user: CurrentUser, db: DbSession) -> None:
    session = _require_owned_session(upload_id, current_user, db)
    if session.status == "active":
        (UPLOADS_DIR / session.temp_filename).unlink(missing_ok=True)
        session.status = "aborted"
        db.commit()
