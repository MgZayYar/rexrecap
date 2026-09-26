"""Tests for Phase 15: resumable uploads and per-user quotas."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.api.routes.uploads as uploads_route
import app.api.routes.videos as videos_route
import app.services.storage as storage_service
from app.api.routes import videos as videos_route_module
from tests.conftest import FAKE_MP4, auth_headers

CHUNK = b"x" * 1024


@pytest.fixture()
def upload_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect storage for both the legacy and resumable upload routes."""
    target = tmp_path / "uploads"
    target.mkdir()
    monkeypatch.setattr(videos_route_module, "UPLOADS_DIR", target)
    monkeypatch.setattr(uploads_route, "UPLOADS_DIR", target)
    return target


def _create_session(client: TestClient, headers: dict[str, str], total: int = 4096,
                    filename: str = "clip.mp4") -> dict:
    response = client.post("/api/videos/uploads", headers=headers, json={
        "filename": filename, "content_type": "video/mp4", "total_bytes": total})
    assert response.status_code == 201, response.text
    return response.json()


def _patch_chunk(client: TestClient, headers: dict[str, str], upload_id: str,
                 offset: int, data: bytes = CHUNK):
    return client.patch(f"/api/videos/uploads/{upload_id}", content=data,
                        headers={**headers, "upload-offset": str(offset)})


def test_resumable_upload_full_cycle(client: TestClient, upload_dirs: Path) -> None:
    headers = auth_headers(client)
    session = _create_session(client, headers)
    assert session["received_bytes"] == 0

    for i in range(4):
        response = _patch_chunk(client, headers, session["id"], i * 1024)
        assert response.status_code == 200, response.text
        assert response.json()["received_bytes"] == (i + 1) * 1024

    # Resume offset is visible to the client.
    response = client.get(f"/api/videos/uploads/{session['id']}", headers=headers)
    assert response.json()["received_bytes"] == 4096

    response = client.post(f"/api/videos/uploads/{session['id']}/complete", headers=headers)
    assert response.status_code == 201, response.text
    video = response.json()
    assert video["filename"] == "clip.mp4"
    assert video["size_bytes"] == 4096
    stored = upload_dirs / [p for p in upload_dirs.iterdir()
                            if p.name != video["id"] and p.suffix == ".mp4"][0].name
    assert stored.stat().st_size == 4096


def test_chunk_offset_mismatch_rejected(client: TestClient, upload_dirs: Path) -> None:
    headers = auth_headers(client)
    session = _create_session(client, headers)
    response = _patch_chunk(client, headers, session["id"], 512)
    assert response.status_code == 409
    assert "0 bytes" in response.json()["detail"]
    # Server offset unchanged; the correct offset still works.
    response = _patch_chunk(client, headers, session["id"], 0)
    assert response.status_code == 200


def test_chunk_requires_offset_header(client: TestClient, upload_dirs: Path) -> None:
    headers = auth_headers(client)
    session = _create_session(client, headers)
    response = client.patch(f"/api/videos/uploads/{session['id']}", headers=headers, content=CHUNK)
    assert response.status_code == 400


def test_complete_rejects_incomplete_upload(client: TestClient, upload_dirs: Path) -> None:
    headers = auth_headers(client)
    session = _create_session(client, headers)
    _patch_chunk(client, headers, session["id"], 0)
    response = client.post(f"/api/videos/uploads/{session['id']}/complete", headers=headers)
    assert response.status_code == 409


def test_abort_deletes_partial_file(client: TestClient, upload_dirs: Path) -> None:
    headers = auth_headers(client)
    session = _create_session(client, headers)
    _patch_chunk(client, headers, session["id"], 0)
    assert len(list(upload_dirs.iterdir())) == 1
    response = client.delete(f"/api/videos/uploads/{session['id']}", headers=headers)
    assert response.status_code == 204
    assert list(upload_dirs.iterdir()) == []
    # Chunks after abort are rejected.
    response = _patch_chunk(client, headers, session["id"], 1024)
    assert response.status_code == 409


def test_sessions_are_user_isolated(client: TestClient, upload_dirs: Path) -> None:
    owner = auth_headers(client, email="sessowner@example.com")
    intruder = auth_headers(client, email="sessintruder@example.com")
    session = _create_session(client, owner)
    assert client.get(f"/api/videos/uploads/{session['id']}", headers=intruder).status_code == 404
    assert _patch_chunk(client, intruder, session["id"], 0).status_code == 404
    assert client.post(f"/api/videos/uploads/{session['id']}/complete",
                       headers=intruder).status_code == 404


def test_session_validates_file_and_project(client: TestClient, upload_dirs: Path) -> None:
    headers = auth_headers(client)
    response = client.post("/api/videos/uploads", headers=headers, json={
        "filename": "notes.txt", "content_type": "text/plain", "total_bytes": 100})
    assert response.status_code == 415
    response = client.post("/api/videos/uploads", headers=headers, json={
        "filename": "clip.mp4", "content_type": "video/mp4", "total_bytes": 10**12})
    assert response.status_code == 413
    response = client.post("/api/videos/uploads", headers=headers, json={
        "filename": "clip.mp4", "content_type": "video/mp4",
        "total_bytes": 100, "project_id": 999999})
    assert response.status_code == 404


def test_quota_enforced_on_session_create(client: TestClient, upload_dirs: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_service, "USER_STORAGE_QUOTA_BYTES", 2048)
    headers = auth_headers(client)
    response = client.post("/api/videos/uploads", headers=headers, json={
        "filename": "clip.mp4", "content_type": "video/mp4", "total_bytes": 4096})
    assert response.status_code == 413


def test_quota_counts_partial_uploads(client: TestClient, upload_dirs: Path,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    headers = auth_headers(client)
    session = _create_session(client, headers, total=4096)
    _patch_chunk(client, headers, session["id"], 0, CHUNK * 2)  # 2048 bytes received
    monkeypatch.setattr(storage_service, "USER_STORAGE_QUOTA_BYTES", 3000)
    # Another 2048-byte chunk would exceed the 3000-byte quota.
    response = _patch_chunk(client, headers, session["id"], 2048, CHUNK * 2)
    assert response.status_code == 413
    # ...and so would a new session.
    response = client.post("/api/videos/uploads", headers=headers, json={
        "filename": "other.mp4", "content_type": "video/mp4", "total_bytes": 1024})
    assert response.status_code == 413


def test_quota_enforced_on_legacy_upload(client: TestClient, upload_dirs: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(videos_route, "USER_STORAGE_QUOTA_BYTES", 100)
    headers = auth_headers(client)
    response = client.post("/api/videos/upload", headers=headers,
                           files={"file": ("clip.mp4", FAKE_MP4, "video/mp4")})
    assert response.status_code == 413
    assert list(upload_dirs.iterdir()) == []


def test_quota_endpoint_reports_usage(client: TestClient, upload_dirs: Path) -> None:
    headers = auth_headers(client)
    session = _create_session(client, headers, total=4096)
    _patch_chunk(client, headers, session["id"], 0, CHUNK * 2)
    response = client.get("/api/videos/quota", headers=headers)
    assert response.status_code == 200, response.text
    quota = response.json()
    assert quota["used_bytes"] == 2048
    assert quota["available_bytes"] == quota["quota_bytes"] - 2048
