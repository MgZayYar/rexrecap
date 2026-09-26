from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Translation(Base):
    __tablename__ = "translations"
    __table_args__ = (UniqueConstraint("transcript_id", "target_language", name="uq_translation_language"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id"), index=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), unique=True, index=True, nullable=False)
    target_language: Mapped[str] = mapped_column(String(16), nullable=False)
    target_language_name: Mapped[str] = mapped_column(String(80), nullable=False)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transcript: Mapped["Transcript"] = relationship(back_populates="translations")
    job: Mapped["ProcessingJob"] = relationship()
