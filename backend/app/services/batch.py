"""Batch runs: queue one job type across many videos, tracked as a group."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.batch_run import BatchRun, BatchRunItem
from app.models.video import Video
from app.services.jobs import create_job_record, enqueue_job

BATCHABLE_JOB_TYPES = frozenset({
    "transcription",
    "translation",
    "dubbing",
    "autocrop",
    "face_detection",
    "subtitle_burn",
    "render",
    "shorts",
    "thumbnails",
})

MAX_BATCH_VIDEOS = 50

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


async def create_batch_run(db: Session, user_id: int, job_type: str,
                           video_ids: list[int], params: dict | None,
                           label: str | None = None) -> BatchRun:
    """Validate ownership, queue one job per video, and group them as a batch.

    Raises ValueError when a video id is not owned by the user.
    """
    if job_type not in BATCHABLE_JOB_TYPES:
        raise ValueError(f"Job type '{job_type}' cannot be batched")
    unique_ids = list(dict.fromkeys(video_ids))
    if not unique_ids:
        raise ValueError("Select at least one video")
    if len(unique_ids) > MAX_BATCH_VIDEOS:
        raise ValueError(f"A batch can cover at most {MAX_BATCH_VIDEOS} videos")

    owned_ids = set(db.scalars(
        select(Video.id).where(Video.id.in_(unique_ids), Video.user_id == user_id)
    ).all())
    foreign = [vid for vid in unique_ids if vid not in owned_ids]
    if foreign:
        raise ValueError(f"Videos not found: {foreign}")

    batch = BatchRun(
        user_id=user_id,
        label=label or f"{job_type} × {len(unique_ids)}",
        job_type=job_type,
    )
    db.add(batch)
    db.flush()

    jobs = []
    for video_id in unique_ids:
        job = create_job_record(db, video_id, job_type, params=params)
        db.add(BatchRunItem(batch_run_id=batch.id, video_id=video_id, job_id=job.id))
        jobs.append(job)
    db.commit()
    db.refresh(batch)
    for job in jobs:
        await enqueue_job(job)
    return batch


def batch_summary(batch: BatchRun) -> dict:
    """Aggregate per-job statuses into a progress summary."""
    counts = {"total": 0, "queued": 0, "processing": 0,
              "completed": 0, "failed": 0, "cancelled": 0}
    for item in batch.items:
        counts["total"] += 1
        status = item.job.status if item.job else "queued"
        counts[status] = counts.get(status, 0) + 1
    if counts["queued"] or counts["processing"]:
        overall = "running"
    elif counts["failed"]:
        overall = "failed"
    elif counts["cancelled"]:
        overall = "cancelled"
    else:
        overall = "completed"
    return {"status": overall, **counts}
