"""Processing-job application service.

Centralizes job creation so API routes don't duplicate the
create -> commit -> refresh -> enqueue sequence.

When a route must create extra rows atomically with the job
(e.g. a Translation row the worker depends on), use
``create_job_record`` to persist the job, create the extra rows,
commit everything, then enqueue with ``enqueue_job``.
"""

from sqlalchemy.orm import Session

from app.models.processing_job import ProcessingJob
from app.workers.queue import job_queue


def create_job_record(db: Session, video_id: int, job_type: str) -> ProcessingJob:
    """Persist a queued job without handing it to the worker queue.

    The caller is responsible for committing and calling
    ``enqueue_job`` once any dependent rows are durable.
    """
    job = ProcessingJob(video_id=video_id, job_type=job_type, status="queued", progress=0)
    db.add(job)
    db.flush()
    return job


async def enqueue_job(job: ProcessingJob) -> None:
    """Hand a persisted job to the worker queue."""
    await job_queue.enqueue(job.id)


async def create_job(db: Session, video_id: int, job_type: str) -> ProcessingJob:
    """Persist a queued job and hand it to the worker queue."""
    job = create_job_record(db, video_id, job_type)
    db.commit()
    db.refresh(job)
    await enqueue_job(job)
    return job
