import asyncio


class InProcessJobQueue:
    """Deduplicated queue for job IDs within one API process."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._queued_ids: set[int] = set()

    async def enqueue(self, job_id: int) -> None:
        if job_id not in self._queued_ids:
            self._queued_ids.add(job_id)
            await self._queue.put(job_id)

    async def dequeue(self) -> int:
        job_id = await self._queue.get()
        self._queued_ids.discard(job_id)
        return job_id


job_queue = InProcessJobQueue()
