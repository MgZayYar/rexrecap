"""Batch runs: one job of the same type across many videos, tracked as a group."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BatchRun(Base):
    __tablename__ = "batch_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["BatchRunItem"]] = relationship(
        back_populates="batch_run", cascade="all, delete-orphan")


class BatchRunItem(Base):
    __tablename__ = "batch_run_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_run_id: Mapped[int] = mapped_column(ForeignKey("batch_runs.id"), index=True,
                                             nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), nullable=False)

    batch_run: Mapped["BatchRun"] = relationship(back_populates="items")
    job: Mapped["ProcessingJob"] = relationship()
    video: Mapped["Video"] = relationship()
