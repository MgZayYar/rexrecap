"""Job queue interface.

The database is the durable queue: the API persists ``ProcessingJob`` rows
with ``status='queued'`` and the standalone worker process
(``python -m app.workers.runner``) claims them. ``enqueue`` is therefore a
no-op kept so job-creation code does not need to know about the transport.
"""


class JobQueue:
    async def enqueue(self, job_id: int) -> None:
        """Record that a persisted job is ready; the worker polls the DB."""


job_queue = JobQueue()
