"""Per-user notification settings (email / webhook for job events)."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

NOTIFICATION_CHANNELS = ("email", "webhook")
NOTIFICATION_EVENTS = ("job_completed", "job_failed", "job_cancelled")


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    """One of NOTIFICATION_CHANNELS."""
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    """Email address or webhook URL."""
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    """Subset of NOTIFICATION_EVENTS."""
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="notification_settings")
