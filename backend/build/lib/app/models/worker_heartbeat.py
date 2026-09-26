"""Worker heartbeats: one row per live worker process.

The standalone worker refreshes its row every poll cycle so the API can
report whether any worker is actually running and what it is doing.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_worker_id() -> str:
    return uuid4().hex


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_worker_id)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                onupdate=func.now())
    current_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
