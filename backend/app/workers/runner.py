"""Standalone worker process: ``python -m app.workers.runner``.

The database is the durable queue: the API persists ``ProcessingJob`` rows
with ``status='queued'`` and this process claims them one at a time with a
single atomic ``UPDATE ... RETURNING`` statement, so any number of worker
processes can run against the same database without double-processing.

Run it as a separate process next to the API server::

    cd backend
    .venv/bin/python -m app.workers.runner

Poll interval comes from ``WORKER_POLL_INTERVAL`` (seconds, default 2.0).
SIGTERM/SIGINT finish the current job, then exit.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.core.config import WORKER_POLL_INTERVAL
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.workers.jobs import JOB_HANDLERS

logger = logging.getLogger("rexcrop.worker")


def claim_next_job() -> tuple[int, str] | None:
    """Atomically claim the oldest queued job.

    The UPDATE and the row selection are one statement, so concurrent
    workers never claim the same job. Returns ``(job_id, job_type)``.
    """
    oldest_queued = (
        select(ProcessingJob.id)
        .where(ProcessingJob.status == "queued")
        .order_by(ProcessingJob.created_at, ProcessingJob.id)
        .limit(1)
        .scalar_subquery()
    )
    with SessionLocal() as db:
        row = db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.status == "queued", ProcessingJob.id == oldest_queued)
            .values(status="processing", started_at=datetime.now(UTC), progress=0)
            .returning(ProcessingJob.id, ProcessingJob.job_type)
        ).first()
        db.commit()
    return (row[0], row[1]) if row else None


def recover_interrupted_jobs() -> int:
    """Requeue jobs left in ``processing`` by a crashed worker.

    Called once at startup; a second worker doing the same is harmless
    because the claim statement only takes ``queued`` rows.
    """
    with SessionLocal() as db:
        result = db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.status == "processing")
            .values(status="queued", started_at=None, progress=0)
        )
        db.commit()
        return result.rowcount


async def _report_progress(job_id: int, progress: int) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is not None and job.status == "processing":
            job.progress = min(max(progress, 0), 100)
            db.commit()


async def process_claimed_job(job_id: int, job_type: str) -> None:
    """Run one claimed job's handler and record its terminal state."""
    logger.info("processing job %s (%s)", job_id, job_type)
    try:
        handler = JOB_HANDLERS[job_type]
        await handler(job_id, lambda progress: _report_progress(job_id, progress))
    except Exception as exc:
        logger.exception("job %s failed", job_id)
        with SessionLocal() as db:
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:1000]
                job.finished_at = datetime.now(UTC)
                db.commit()
        return
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is not None:
            job.status = "completed"
            job.progress = 100
            job.finished_at = datetime.now(UTC)
            db.commit()
    logger.info("job %s completed", job_id)


async def run_once() -> bool:
    """Claim and process a single job. Returns True when a job ran."""
    claimed = await asyncio.to_thread(claim_next_job)
    if claimed is None:
        return False
    job_id, job_type = claimed
    await process_claimed_job(job_id, job_type)
    return True


async def run_forever(stop_event: asyncio.Event) -> None:
    recovered = await asyncio.to_thread(recover_interrupted_jobs)
    if recovered:
        logger.info("requeued %d interrupted job(s)", recovered)
    logger.info("worker started (poll interval %.1fs)", WORKER_POLL_INTERVAL)
    while not stop_event.is_set():
        try:
            processed = await run_once()
        except Exception:
            logger.exception("worker iteration failed")
            processed = False
        if not processed:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=WORKER_POLL_INTERVAL)
            except TimeoutError:
                pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    stop_event = asyncio.Event()
    loop = asyncio.new_event_loop()

    def _request_stop(*_args: object) -> None:
        logger.info("shutdown requested; finishing current job")
        loop.call_soon_threadsafe(stop_event.set)

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _request_stop)
    try:
        loop.run_until_complete(run_forever(stop_event))
    finally:
        loop.close()
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
