"""FaceAnalysis: stored result of the face detection/tracking service.

One row per video (replaced on re-analysis). The `result` JSON is the
FaceAnalysisResult dict: people with persistent person IDs, timestamps,
and per-frame bounding boxes. Downstream features (smart crop, shorts)
read this instead of re-running detection.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FaceAnalysis(Base):
    __tablename__ = "face_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
