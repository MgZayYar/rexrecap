from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    """Relative path (under storage/outputs) of the user-selected thumbnail."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="videos")
    project: Mapped["Project | None"] = relationship(back_populates="videos")
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    short_clips: Mapped[list["ShortClip"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    thumbnails: Mapped[list["Thumbnail"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    transcript: Mapped["Transcript | None"] = relationship(back_populates="video", cascade="all, delete-orphan", uselist=False)
