"""Tests for batch runs: multi-video job creation, summaries, and ownership."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.batch_run import BatchRun, BatchRunItem
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from app.services.batch import batch_summary
from tests.conftest import auth_headers


def _seed_videos(db_session: Session, email: str, count: int) -> tuple[User, list[Video]]:
    user = User(email=email, password_hash="x")
    db_session.add(user)
    db_session.flush()
    videos = []
    for index in range(count):
        video = Video(user_id=user.id, filename=f"clip{index}.mp4",
                      stored_filename=f"stored{index}.mp4",
                      content_type="video/mp4", size_bytes=1234)
        db_session.add(video)
        videos.append(video)
    db_session.flush()
    db_session.commit()
    return user, videos


def test_create_batch_queues_one_job_per_video(client: TestClient,
                                               db_session: Session) -> None:
    headers = auth_headers(client, email="batch@example.com")
    api_user = db_session.query(User).filter_by(email="batch@example.com").first()
    _, videos = _seed_videos(db_session, "batchseed@example.com", 3)
    for video in videos:
        video.user_id = api_user.id
    db_session.commit()

    video_ids = [v.id for v in videos]
    response = client.post("/api/batch/runs", headers=headers, json={
        "job_type": "transcription",
        "video_ids": video_ids,
        "label": "Weekly recaps",
    })
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["label"] == "Weekly recaps"
    assert payload["job_type"] == "transcription"
    assert payload["summary"]["total"] == 3
    assert payload["summary"]["status"] == "running"

    items = db_session.scalars(
        select(BatchRunItem).where(BatchRunItem.batch_run_id == payload["id"])
    ).all()
    assert len(items) == 3
    assert {item.video_id for item in items} == set(video_ids)

    # Detail view shows per-video job state.
    response = client.get(f"/api/batch/runs/{payload['id']}", headers=headers)
    assert response.status_code == 200
    detail = response.json()
    assert len(detail["items"]) == 3
    assert all(item["job_status"] == "queued" for item in detail["items"])

    # Simulate the worker finishing everything: summary flips to completed.
    jobs = db_session.scalars(select(ProcessingJob)).all()
    for job in jobs:
        job.status = "completed"
        job.progress = 100
    db_session.commit()
    response = client.get(f"/api/batch/runs/{payload['id']}", headers=headers)
    assert response.json()["summary"]["status"] == "completed"
    assert response.json()["summary"]["completed"] == 3


def test_batch_rejects_foreign_and_unknown_videos(client: TestClient,
                                                  db_session: Session) -> None:
    alice = auth_headers(client, email="batchalice@example.com")
    bob = auth_headers(client, email="batchbob@example.com")
    bob_user = db_session.query(User).filter_by(email="batchbob@example.com").first()
    _, videos = _seed_videos(db_session, "batchseed2@example.com", 1)
    videos[0].user_id = bob_user.id
    db_session.commit()
    foreign_id = videos[0].id

    response = client.post("/api/batch/runs", headers=alice, json={
        "job_type": "transcription", "video_ids": [foreign_id],
    })
    assert response.status_code == 400
    assert db_session.scalars(select(BatchRun)).all() == []

    response = client.post("/api/batch/runs", headers=alice, json={
        "job_type": "transcription", "video_ids": [999999],
    })
    assert response.status_code == 400

    response = client.post("/api/batch/runs", headers=alice, json={
        "job_type": "nope", "video_ids": [foreign_id],
    })
    assert response.status_code == 400

    # Bob's own batch is invisible to Alice.
    response = client.post("/api/batch/runs", headers=bob, json={
        "job_type": "transcription", "video_ids": [foreign_id],
    })
    batch_id = response.json()["id"]
    assert client.get(f"/api/batch/runs/{batch_id}", headers=alice).status_code == 404
    assert client.get("/api/batch/runs", headers=alice).json() == []


def test_batch_summary_status_precedence(db_session: Session) -> None:
    user, videos = _seed_videos(db_session, "batchsum@example.com", 2)

    async def _make() -> BatchRun:
        from app.services.batch import create_batch_run
        return await create_batch_run(db_session, user.id, "thumbnails",
                                      [v.id for v in videos], {})

    batch = asyncio.run(_make())
    assert batch_summary(batch)["status"] == "running"

    jobs = db_session.scalars(select(ProcessingJob)).all()
    jobs[0].status = "failed"
    jobs[1].status = "completed"
    assert batch_summary(batch)["status"] == "failed"

    jobs[0].status = "cancelled"
    assert batch_summary(batch)["status"] == "cancelled"

    jobs[0].status = "completed"
    assert batch_summary(batch)["status"] == "completed"
