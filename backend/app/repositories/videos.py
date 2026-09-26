"""Ownership-scoped video queries shared by API routes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.video import Video


def get_owned_video(db: Session, video_id: int, user_id: int) -> Video | None:
    """Return the video only when it belongs to the given user."""
    return db.scalar(select(Video).where(Video.id == video_id, Video.user_id == user_id))
