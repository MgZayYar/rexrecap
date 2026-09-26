"""Local filesystem storage backend (the default)."""

from __future__ import annotations

from pathlib import Path

from app.storage.base import StorageBackend


class LocalStorageBackend:
    name = "local"

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError(f"Storage key escapes root: {key!r}")
        return path

    def put_file(self, key: str, path: Path, content_type: str | None = None) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(path).read_bytes())

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def presigned_get_url(self, key: str, expires_in: int = 3600,
                          filename: str | None = None) -> str:
        raise NotImplementedError("Local storage serves files through the API")
