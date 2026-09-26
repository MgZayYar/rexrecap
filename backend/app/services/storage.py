"""Per-user storage quota accounting.

Usage counts finished videos plus bytes already received by active
resumable-upload sessions, so a user cannot dodge the quota by leaving
uploads half-finished.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import USER_STORAGE_QUOTA_BYTES
from app.models.upload_session import UploadSession
from app.models.video import Video


class QuotaExceededError(Exception):
    """Raised when an upload would push a user over their storage quota."""


def storage_usage_bytes(db: Session, user_id: int) -> int:
    videos = db.scalar(
        select(func.coalesce(func.sum(Video.size_bytes), 0)).where(Video.user_id == user_id)
    ) or 0
    partial = db.scalar(
        select(func.coalesce(func.sum(UploadSession.received_bytes), 0)).where(
            UploadSession.user_id == user_id, UploadSession.status == "active")
    ) or 0
    return int(videos) + int(partial)


def check_quota(db: Session, user_id: int, additional_bytes: int) -> None:
    """Raise QuotaExceededError if `additional_bytes` would exceed the quota."""
    if additional_bytes < 0:
        return
    if storage_usage_bytes(db, user_id) + additional_bytes > USER_STORAGE_QUOTA_BYTES:
        raise QuotaExceededError(
            f"Storage quota exceeded ({USER_STORAGE_QUOTA_BYTES // (1024**3)} GB per user)")
