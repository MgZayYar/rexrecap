import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.db.base import Base
from app.db.session import engine
from app.models import ProcessingJob, Transcript, Translation, User, Video  # noqa: F401 - registers model metadata
from app.workers.queue import job_queue
from app.workers.worker import JobWorker


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    worker_task = asyncio.create_task(JobWorker(job_queue).run())
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


def create_application() -> FastAPI:
    app = FastAPI(title="RexCrop API", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router, prefix="/api")
    return app


app = create_application()
