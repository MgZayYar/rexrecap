"""Processing-job creation tests (via the shared job service)."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video
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


def test_list_jobs_limit_is_enforced(client: TestClient, db_session: Session) -> None:
    headers = auth_headers(client, email="joblimit@example.com")
    user = db_session.query(User).filter_by(email="joblimit@example.com").first()
    video = Video(user_id=user.id, filename="v.mp4", stored_filename="s.mp4",
                  content_type="video/mp4", size_bytes=10)
    db_session.add(video)
    db_session.flush()
    for _ in range(5):
        db_session.add(ProcessingJob(video_id=video.id, job_type="transcription",
                                     status="completed", progress=100))
    db_session.commit()

    response = client.get("/api/jobs?limit=2", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get("/api/jobs?limit=0", headers=headers)
    assert response.status_code == 422

    response = client.get("/api/jobs", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 5


def test_job_query_indexes_exist() -> None:
    import importlib.util
    from pathlib import Path

    from sqlalchemy import create_engine, inspect

    from app.db.base import Base
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location(
        "migration_0014", Path("alembic/versions/0014_job_query_indexes.py"))
    migration_0014 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_0014)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration_0014.upgrade()
    indexes = {idx["name"] for idx in inspect(engine).get_indexes("processing_jobs")}
    assert "ix_processing_jobs_video_created" in indexes
    assert "ix_processing_jobs_status_created" in indexes
