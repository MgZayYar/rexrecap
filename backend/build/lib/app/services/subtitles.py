"""Subtitle segment resolution for workers.

Workers that need subtitle text (burn-in, render) share this: given a video,
a source ("transcript" or "translation") and an optional language, return the
segment list or None when the required transcript/translation is missing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transcript import Transcript
from app.models.translation import Translation


def resolve_subtitle_segments(db: Session, video_id: int, source: str = "transcript",
                              language: str | None = None) -> list[dict] | None:
    """Return [{start, end, text}] segments, or None when unavailable."""
    transcript = db.scalar(select(Transcript).where(Transcript.video_id == video_id))
    if transcript is None or not transcript.segments:
        return None
    if source != "translation":
        return list(transcript.segments)
    query = (
        select(Translation)
        .join(Transcript, Translation.transcript_id == Transcript.id)
        .where(Transcript.video_id == video_id)
    )
    if language:
        query = query.where(Translation.target_language == language)
    translation = db.scalar(query.order_by(Translation.created_at.desc()))
    if translation is None or not translation.segments:
        return None
    return list(translation.segments)
