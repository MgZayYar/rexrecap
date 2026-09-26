from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True, nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Relative path under storage/outputs/ for jobs that produce a file."""
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    """Per-job worker options, e.g. dubbing voice/provider."""
    cancel_requested: Mapped[bool] = mapped_column(nullable=False, default=False)
    """Cooperative cancel flag: the worker aborts the job at its next progress check."""

    video: Mapped["Video"] = relationship(back_populates="processing_jobs")
