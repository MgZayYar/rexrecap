"""Storage backend contract.

Two implementations exist: local filesystem (default) and S3-compatible
object storage. Job outputs synced to the remote backend are delivered to
clients as presigned-URL redirects, so the API never proxies large bytes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    name: str

    def put_file(self, key: str, path: Path, content_type: str | None = None) -> None:
        """Upload a local file to `key`."""
        ...

    def exists(self, key: str) -> bool:
        ...

    def delete(self, key: str) -> None:
        ...

    def presigned_get_url(self, key: str, expires_in: int = 3600,
                          filename: str | None = None) -> str:
        """A time-limited direct-download URL. Raises if unsupported."""
        ...
