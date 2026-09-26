"""Job-event notifications: email (SMTP) and webhooks.

Called by the worker when a job reaches a terminal state. Every send is
wrapped in try/except and runs with timeouts — a notification failure is
logged but never fails the job.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy import select

from app.core.config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_TLS,
)
from app.db.session import SessionLocal
from app.models.notification_setting import NOTIFICATION_EVENTS, NotificationSetting
from app.models.processing_job import ProcessingJob
from app.models.video import Video

logger = logging.getLogger("rexcrop.notifications")

_TERMINAL_EVENTS = {
    "completed": "job_completed",
    "failed": "job_failed",
    "cancelled": "job_cancelled",
}


def _webhook_payload(job: ProcessingJob, video: Video | None) -> dict:
    return {
        "event": _TERMINAL_EVENTS[job.status],
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "video_id": job.video_id,
        "video_filename": video.filename if video else None,
        "progress": job.progress,
        "error_message": job.error_message,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _send_email(to_address: str, subject: str, body: str) -> None:
    if not SMTP_HOST:
        logger.warning("SMTP_HOST is not configured; skipping email to %s", to_address)
        return
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USERNAME:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD or "")
        smtp.send_message(message)
    logger.info("Sent job notification email to %s", to_address)


def _send_webhook(url: str, payload: dict) -> None:
    response = httpx.post(url, json=payload, timeout=10,
                          headers={"X-RexCrop-Event": payload["event"]})
    response.raise_for_status()
    logger.info("Delivered job webhook to %s (status %s)", url, response.status_code)


def _describe(job: ProcessingJob, video: Video | None) -> tuple[str, str]:
    name = video.filename if video else f"video {job.video_id}"
    event = _TERMINAL_EVENTS[job.status]
    if event == "job_completed":
        subject = f"RexCrop: {job.job_type} job completed"
        body = (f"Your {job.job_type} job for '{name}' finished successfully.\n"
                f"Job #{job.id} completed at {job.finished_at}.\n")
    elif event == "job_failed":
        subject = f"RexCrop: {job.job_type} job failed"
        body = (f"Your {job.job_type} job for '{name}' failed.\n"
                f"Error: {job.error_message or 'unknown'}\n")
    else:
        subject = f"RexCrop: {job.job_type} job cancelled"
        body = f"Your {job.job_type} job for '{name}' was cancelled.\n"
    return subject, body


def dispatch_job_notifications(job_id: int) -> None:
    """Notify the job owner's enabled settings about the terminal event."""
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None or job.status not in _TERMINAL_EVENTS:
            return
        event = _TERMINAL_EVENTS[job.status]
        video = db.get(Video, job.video_id)
        user_id = video.user_id if video else None
        settings = db.scalars(
            select(NotificationSetting).where(
                NotificationSetting.user_id == user_id,
                NotificationSetting.enabled.is_(True))
        ).all() if user_id else []
        subject, body = _describe(job, video)
        payload = _webhook_payload(job, video)

    for setting in settings:
        if event not in (setting.events or []):
            continue
        try:
            if setting.channel == "email":
                _send_email(setting.target, subject, body)
            elif setting.channel == "webhook":
                _send_webhook(setting.target, payload)
        except Exception:
            logger.exception("Notification via %s to %s failed",
                             setting.channel, setting.target)


def send_test_notification(setting_id: int, user_id: int) -> None:
    """Send a test ping through one of the user's settings; raises on failure."""
    with SessionLocal() as db:
        setting = db.scalar(
            select(NotificationSetting).where(
                NotificationSetting.id == setting_id,
                NotificationSetting.user_id == user_id))
        if setting is None:
            raise ValueError("Notification setting not found")
        channel, target = setting.channel, setting.target
    if channel == "email":
        _send_email(target, "RexCrop: test notification",
                    "This is a test notification from RexCrop. Your email alerts are working.")
    elif channel == "webhook":
        _send_webhook(target, {"event": "test", "message": "RexCrop test notification"})
    else:
        raise ValueError(f"Unknown channel: {channel}")
