"""Video upload validation tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import videos as videos_route
from tests.conftest import FAKE_MP4, auth_headers, upload


def test_upload_rejects_disallowed_extension(client: TestClient, uploads_dir: Path):
    headers = auth_headers(client)
    response = upload(client, headers, "notes.txt", b"hello", "text/plain")
    assert response.status_code == 415
    assert list(uploads_dir.iterdir()) == []


def test_upload_rejects_empty_file(client: TestClient, uploads_dir: Path):
    headers = auth_headers(client)
    response = upload(client, headers, "empty.mp4", b"", "video/mp4")
    assert response.status_code == 400
    assert list(uploads_dir.iterdir()) == []


def test_upload_stores_file_with_safe_name(client: TestClient, uploads_dir: Path):
    headers = auth_headers(client)
    response = upload(client, headers, "../../evil.mp4", FAKE_MP4, "video/mp4")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "evil.mp4"
    assert body["size_bytes"] == len(FAKE_MP4)

    stored = list(uploads_dir.iterdir())
    assert len(stored) == 1
    assert stored[0].name != "evil.mp4"
    assert stored[0].suffix == ".mp4"


def test_upload_enforces_size_limit(client: TestClient, uploads_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(videos_route, "MAX_UPLOAD_BYTES", 512)
    headers = auth_headers(client)
    response = upload(client, headers, "big.mp4", FAKE_MP4, "video/mp4")
    assert response.status_code == 413
    assert list(uploads_dir.iterdir()) == []


def test_videos_are_isolated_between_users(client: TestClient, uploads_dir: Path):
    owner = auth_headers(client, email="owner@example.com")
    stranger = auth_headers(client, email="stranger@example.com")

    created = upload(client, owner, "clip.mp4", FAKE_MP4, "video/mp4")
    video_id = created.json()["id"]

    assert client.get("/api/videos", headers=stranger).json() == []
    assert client.get(f"/api/videos/{video_id}/download", headers=stranger).status_code == 404
