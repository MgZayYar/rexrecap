"""Unauthenticated health endpoint for load balancers and compose probes."""

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger("rexcrop.health")

router = APIRouter()


def _check_database() -> str | None:
    """Return None when healthy, otherwise an error description."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - surfaced in the payload
        return str(exc)
    return None


def _check_storage() -> str | None:
    from app import storage as storage_pkg
    from app.core.config import OUTPUTS_DIR, UPLOADS_DIR

    try:
        if not storage_pkg.is_remote_delivery():
            for directory in (UPLOADS_DIR, OUTPUTS_DIR):
                directory.mkdir(parents=True, exist_ok=True)
                if not os.access(directory, os.W_OK):
                    return f"{directory} is not writable"
            return None
        backend = storage_pkg.get_storage_backend()
        # A cheap existence probe also proves the bucket is reachable.
        backend.exists("__healthcheck__")
    except Exception as exc:  # noqa: BLE001 - surfaced in the payload
        return str(exc)
    return None


@router.get("/health")
def health() -> JSONResponse:
    database_error = _check_database()
    storage_error = _check_storage()
    healthy = database_error is None and storage_error is None
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "database": "ok" if database_error is None else f"error: {database_error}",
            "storage": "ok" if storage_error is None else f"error: {storage_error}",
        },
    )
