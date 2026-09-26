"""Shared pytest fixtures: isolated temp SQLite database per test."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.api.routes import videos as videos_route
from app.db.base import Base
from app.main import app

FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1024


@pytest.fixture()
def db_session() -> Iterator[Session]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.unlink(path)


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # NOTE: no lifespan context, so the background worker never starts in tests.
    test_client = TestClient(app, raise_server_exceptions=False)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


def auth_headers(client: TestClient, email: str = "user@example.com") -> dict[str, str]:
    client.post("/api/auth/register", json={"email": email, "password": "secret1234"})
    response = client.post("/api/auth/login", json={"email": email, "password": "secret1234"})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def uploads_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect video storage to a temp dir so tests never touch real uploads."""
    target = tmp_path / "uploads"
    target.mkdir()
    monkeypatch.setattr(videos_route, "UPLOADS_DIR", target)
    return target


def upload(client: TestClient, headers: dict[str, str], filename: str, content: bytes, content_type: str):
    return client.post(
        "/api/videos/upload",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )
