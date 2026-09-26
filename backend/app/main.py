import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import DEFAULT_JWT_SECRET_KEY, JWT_SECRET_KEY
from app.db.migrations import run_migrations
from app.models import ProcessingJob, Project, Transcript, Translation, User, Video  # noqa: F401 - registers model metadata
from app.workers.queue import job_queue
from app.workers.worker import JobWorker

logger = logging.getLogger("rexcrop")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if JWT_SECRET_KEY == DEFAULT_JWT_SECRET_KEY:
        logger.warning(
            "Using the default development JWT_SECRET_KEY. Set JWT_SECRET_KEY in backend/.env before deployment."
        )
    # Alembic owns the schema: this converges fresh and existing databases
    # to the current revision without destroying data.
    run_migrations()
    worker_task = asyncio.create_task(JobWorker(job_queue).run())
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning("HTTP %s on %s: %s", exc.status_code, request.url.path, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def create_application() -> FastAPI:
    app = FastAPI(title="RexCrop API", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    # Canonical versioned routes; the unversioned prefix stays for backward compatibility.
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(api_router, prefix="/api")
    return app


app = create_application()
