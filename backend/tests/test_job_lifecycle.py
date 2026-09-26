"""Tests for Phase 16: job cancellation, retry, and worker heartbeats."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

import app.workers.runner as runner
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.models.worker_heartbeat import WorkerHeartbeat
from tests.conftest import auth_headers


@pytest.fixture()
def runner_db(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    """Point the runner's sessions at the test database."""
    def factory():
        class Ctx:
            def __enter__(self):
                return db_session
            def __exit__(self, *args):
                return False
        return Ctx()
    monkeypatch.setattr(runner, "SessionLocal", factory)
    return db_session


def _video(db_session: Session, user_id: int) -> Video:
    name = f"c-{uuid4().hex}.mp4"
    video = Video(user_id=user_id, filename=name, stored_filename=name,
                  content_type="video/mp4", size_bytes=10)
    db_session.add(video)
    db_session.commit()
    return video


def _identity(client: TestClient, email: str) -> tuple[int, dict[str, str]]:
    """Register+login once; return (user_id, auth headers) for the same user."""
    headers = auth_headers(client, email=email)
    response = client.get("/api/auth/me", headers=headers)
    return response.json()["id"], headers


def _job(client: TestClient, db_session: Session, user_id: int, status: str = "queued") -> ProcessingJob:
    video = _video(db_session, user_id)
    job = ProcessingJob(video_id=video.id, job_type="render", status=status, progress=0)
    db_session.add(job)
    db_session.commit()
    return job


def test_cancel_queued_job(client: TestClient, db_session: Session) -> None:
    user_id, headers = _identity(client, "lifecycle@example.com")
    job = _job(client, db_session, user_id)
    response = client.post(f"/api/jobs/{job.id}/cancel", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    db_session.refresh(job)
    assert job.status == "cancelled" and job.finished_at is not None


def test_cancel_terminal_job_conflicts(client: TestClient, db_session: Session) -> None:
    user_id, headers = _identity(client, "term@example.com")
    job = _job(client, db_session, user_id, status="completed")
    assert client.post(f"/api/jobs/{job.id}/cancel", headers=headers).status_code == 409


def test_cancel_processing_job_aborts_at_next_checkpoint(
        client: TestClient, runner_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, headers = _identity(client, "proccancel@example.com")
    job = _job(client, runner_db, user_id, status="processing")

    async def slow_handler(job_id: int, report):
        await report(10)
        await report(20)  # never reached: cancel is requested before the first report

    monkeypatch.setitem(runner.JOB_HANDLERS, "render", slow_handler)
    response = client.post(f"/api/jobs/{job.id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["cancel_requested"] is True

    import asyncio
    asyncio.run(runner.process_claimed_job(job.id, "render"))
    runner_db.refresh(job)
    assert job.status == "cancelled"
    assert job.finished_at is not None


def test_retry_failed_job(client: TestClient, db_session: Session) -> None:
    user_id, headers = _identity(client, "retry@example.com")
    job = _job(client, db_session, user_id, status="failed")
    job.error_message = "boom"
    db_session.commit()
    response = client.post(f"/api/jobs/{job.id}/retry", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "queued" and body["progress"] == 0
    assert body["error_message"] is None and body["cancel_requested"] is False


def test_retry_active_or_completed_job_conflicts(client: TestClient, db_session: Session) -> None:
    user_id, headers = _identity(client, "retry2@example.com")
    for bad_status in ("queued", "processing", "completed"):
        job = _job(client, db_session, user_id, status=bad_status)
        assert client.post(f"/api/jobs/{job.id}/retry", headers=headers).status_code == 409


def test_cancel_and_retry_are_user_isolated(client: TestClient, db_session: Session) -> None:
    owner_id, _ = _identity(client, "iso-owner@example.com")
    _, intruder_headers = _identity(client, "iso-intruder@example.com")
    job = _job(client, db_session, owner_id)
    assert client.post(f"/api/jobs/{job.id}/cancel", headers=intruder_headers).status_code == 404
    job.status = "failed"
    db_session.commit()
    assert client.post(f"/api/jobs/{job.id}/retry", headers=intruder_headers).status_code == 404


def test_jobs_list_filters_and_isolation(client: TestClient, db_session: Session) -> None:
    user_id, headers = _identity(client, "list@example.com")
    other_id, _ = _identity(client, "list-other@example.com")
    _job(client, db_session, user_id, status="completed")
    _job(client, db_session, user_id, status="failed")
    _job(client, db_session, other_id, status="failed")

    response = client.get("/api/jobs", headers=headers)
    assert response.status_code == 200, response.text
    assert {j["status"] for j in response.json()} == {"completed", "failed"}

    response = client.get("/api/jobs", headers=headers, params={"status": "failed"})
    assert [j["status"] for j in response.json()] == ["failed"]

    # Newest first.
    response = client.get("/api/jobs", headers=headers)
    ids = [j["id"] for j in response.json()]
    assert ids == sorted(ids, reverse=True)


def test_worker_heartbeat_and_workers_endpoint(
        client: TestClient, runner_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = auth_headers(client, email="heartbeat@example.com")
    runner.heartbeat("worker-abc", None)
    row = runner_db.get(WorkerHeartbeat, "worker-abc")
    assert row is not None and row.current_job_id is None

    runner.heartbeat("worker-abc", 42)
    runner_db.refresh(row)
    assert row.current_job_id == 42

    response = client.get("/api/jobs/workers", headers=headers)
    assert response.status_code == 200, response.text
    workers = response.json()
    assert any(w["worker_id"] == "worker-abc" and w["is_live"] for w in workers)
