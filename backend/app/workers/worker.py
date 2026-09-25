import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.workers.jobs import JOB_HANDLERS
from app.workers.queue import InProcessJobQueue


class JobWorker:
    def __init__(self, queue: InProcessJobQueue) -> None:
        self.queue = queue

    async def enqueue_persisted_jobs(self) -> None:
        with SessionLocal() as db:
            queued_jobs = db.scalars(select(ProcessingJob.id).where(ProcessingJob.status == "queued")).all()
        for job_id in queued_jobs:
            await self.queue.enqueue(job_id)

    async def run(self) -> None:
        await self.enqueue_persisted_jobs()
        while True:
            try:
                job_id = await asyncio.wait_for(self.queue.dequeue(), timeout=2)
            except TimeoutError:
                await self.enqueue_persisted_jobs()
                continue
            await self.process(job_id)

    async def process(self, job_id: int) -> None:
        with SessionLocal() as db:
            job = db.get(ProcessingJob, job_id)
            if job is None or job.status != "queued":
                return
            job.status = "processing"
            job.started_at = datetime.now(UTC)
            job.progress = 0
            db.commit()
            job_type = job.job_type

        async def update_progress(progress: int) -> None:
            with SessionLocal() as progress_db:
                processing_job = progress_db.get(ProcessingJob, job_id)
                if processing_job is not None and processing_job.status == "processing":
                    processing_job.progress = min(max(progress, 0), 100)
                    progress_db.commit()

        try:
            handler = JOB_HANDLERS[job_type]
            await handler(job_id, update_progress)
            with SessionLocal() as db:
                job = db.get(ProcessingJob, job_id)
                if job is not None:
                    job.status = "completed"
                    job.progress = 100
                    job.finished_at = datetime.now(UTC)
                    db.commit()
        except Exception as exc:
            with SessionLocal() as db:
                job = db.get(ProcessingJob, job_id)
                if job is not None:
                    job.status = "failed"
                    job.error_message = str(exc)[:1000]
                    job.finished_at = datetime.now(UTC)
                    db.commit()
