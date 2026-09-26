"""Storage backend selection from configuration."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import (
    OUTPUTS_DIR,
    PRESIGNED_URL_EXPIRES_IN,
    S3_ACCESS_KEY_ID,
    S3_BUCKET,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
    STORAGE_BACKEND,
)
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend

logger = logging.getLogger("rexcrop.storage")


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    if STORAGE_BACKEND == "s3":
        return S3StorageBackend(
            bucket=S3_BUCKET,
            endpoint_url=S3_ENDPOINT_URL,
            region=S3_REGION,
            access_key_id=S3_ACCESS_KEY_ID,
            secret_access_key=S3_SECRET_ACCESS_KEY,
        )
    return LocalStorageBackend(OUTPUTS_DIR)


def is_remote_delivery() -> bool:
    """True when job outputs should be synced to (and served from) object storage."""
    return STORAGE_BACKEND == "s3" and bool(S3_BUCKET)


def remote_key_for_output(filename: str) -> str:
    return f"outputs/{filename}"


def remote_download_url(remote_key: str | None, filename: str) -> str | None:
    """Presigned direct-download URL, or None when remote delivery is off.

    Never raises: signing failures fall back to local API delivery.
    """
    if not remote_key or not is_remote_delivery():
        return None
    try:
        return get_storage_backend().presigned_get_url(
            remote_key, expires_in=PRESIGNED_URL_EXPIRES_IN, filename=filename)
    except Exception:
        logger.exception("Could not sign remote download URL for %s", remote_key)
        return None
