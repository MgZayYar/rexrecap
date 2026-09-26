"""Highlight clips ("shorts") cut from a video."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ShortClip(Base):
    __tablename__ = "short_clips"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), index=True, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_path: Mapped[str] = mapped_column(Text, nullable=False)
    """Filename under storage/outputs/."""
    remote_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Object-storage key when the clip was synced for remote delivery."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    video: Mapped["Video"] = relationship(back_populates="short_clips")
    job: Mapped["ProcessingJob"] = relationship()
