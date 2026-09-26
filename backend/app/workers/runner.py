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
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.core.config import WORKER_POLL_INTERVAL
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.worker_heartbeat import WorkerHeartbeat, new_worker_id
from app.workers.jobs import JOB_HANDLERS

logger = logging.getLogger("rexcrop.worker")


class JobCancelled(Exception):
    """Raised inside a worker when the user cancels the running job."""


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


def _cancel_requested(job_id: int) -> bool:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        return bool(job is not None and job.cancel_requested)


async def _report_progress(job_id: int, progress: int) -> None:
    """Record progress; raises JobCancelled when the user cancelled the job.

    Every handler reports progress at stage boundaries, so cancellation is
    honored as soon as the current stage finishes.
    """
    if _cancel_requested(job_id):
        raise JobCancelled(f"job {job_id} cancelled by user")
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is not None and job.status == "processing":
            job.progress = min(max(progress, 0), 100)
            db.commit()


def _finish_cancelled(job_id: int) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is not None:
            job.status = "cancelled"
            job.finished_at = datetime.now(UTC)
            db.commit()


async def process_claimed_job(job_id: int, job_type: str) -> None:
    """Run one claimed job's handler and record its terminal state."""
    logger.info("processing job %s (%s)", job_id, job_type)
    if _cancel_requested(job_id):
        logger.info("job %s was cancelled before it started", job_id)
        _finish_cancelled(job_id)
        return
    try:
        handler = JOB_HANDLERS[job_type]
        await handler(job_id, lambda progress: _report_progress(job_id, progress))
    except JobCancelled:
        logger.info("job %s cancelled", job_id)
        _finish_cancelled(job_id)
        return
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


def heartbeat(worker_id: str, current_job_id: int | None) -> None:
    """Upsert this worker's heartbeat row; prune rows stale for over a day."""
    with SessionLocal() as db:
        row = db.get(WorkerHeartbeat, worker_id)
        if row is None:
            db.add(WorkerHeartbeat(worker_id=worker_id, current_job_id=current_job_id))
        else:
            row.current_job_id = current_job_id
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.last_seen < cutoff))
        db.commit()


async def run_once() -> bool:
    """Claim and process a single job. Returns True when a job ran."""
    claimed = await asyncio.to_thread(claim_next_job)
    if claimed is None:
        return False
    job_id, job_type = claimed
    await process_claimed_job(job_id, job_type)
    return True


async def run_forever(stop_event: asyncio.Event) -> None:
    worker_id = new_worker_id()
    recovered = await asyncio.to_thread(recover_interrupted_jobs)
    if recovered:
        logger.info("requeued %d interrupted job(s)", recovered)
    logger.info("worker %s started (poll interval %.1fs)", worker_id, WORKER_POLL_INTERVAL)
    current: dict[str, int | None] = {"job_id": None}

    async def heartbeat_loop() -> None:
        while not stop_event.is_set():
            await asyncio.to_thread(heartbeat, worker_id, current["job_id"])
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=WORKER_POLL_INTERVAL)
            except TimeoutError:
                pass

    beat_task = asyncio.create_task(heartbeat_loop())
    try:
        while not stop_event.is_set():
            try:
                claimed = await asyncio.to_thread(claim_next_job)
            except Exception:
                logger.exception("worker iteration failed")
                claimed = None
            if claimed is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=WORKER_POLL_INTERVAL)
                except TimeoutError:
                    pass
                continue
            job_id, job_type = claimed
            current["job_id"] = job_id
            try:
                await process_claimed_job(job_id, job_type)
            except Exception:
                logger.exception("worker iteration failed")
            finally:
                current["job_id"] = None
    finally:
        beat_task.cancel()
        try:
            await beat_task
        except asyncio.CancelledError:
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
