"""Processing-job creation tests (via the shared job service)."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import FAKE_MP4, auth_headers, upload


def _owned_video_id(client: TestClient, headers: dict[str, str], uploads_dir: Path) -> int:
    response = upload(client, headers, "clip.mp4", FAKE_MP4, "video/mp4")
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_job_queues_work(client: TestClient, uploads_dir: Path):
    headers = auth_headers(client)
    video_id = _owned_video_id(client, headers, uploads_dir)

    response = client.post("/api/jobs/create", json={"video_id": video_id, "job_type": "dubbing"}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["video_id"] == video_id
    assert body["job_type"] == "dubbing"
    assert body["status"] == "queued"
    assert body["progress"] == 0


def test_create_job_rejects_unknown_video(client: TestClient, uploads_dir: Path):
    headers = auth_headers(client)
    response = client.post("/api/jobs/create", json={"video_id": 999999, "job_type": "autocrop"}, headers=headers)
    assert response.status_code == 404


def test_create_job_rejects_other_users_video(client: TestClient, uploads_dir: Path):
    owner = auth_headers(client, email="owner@example.com")
    stranger = auth_headers(client, email="stranger@example.com")
    video_id = _owned_video_id(client, owner, uploads_dir)

    response = client.post("/api/jobs/create", json={"video_id": video_id, "job_type": "render"}, headers=stranger)
    assert response.status_code == 404


def test_start_transcription_uses_job_service(client: TestClient, uploads_dir: Path):
    headers = auth_headers(client)
    video_id = _owned_video_id(client, headers, uploads_dir)

    response = client.post(f"/api/transcripts/start/{video_id}", headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["job_type"] == "transcription"
    assert response.json()["status"] == "queued"


def test_versioned_api_prefix_serves_projects(client: TestClient):
    headers = auth_headers(client)
    created = client.post("/api/v1/projects", json={"name": "V1"}, headers=headers)
    assert created.status_code == 201, created.text
    listed = client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    assert [p["name"] for p in listed.json()] == ["V1"]
