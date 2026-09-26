"""Tests for Phase 9 face detection: tracker, service, worker, and API."""

import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.workers.jobs.face_detection as face_detection_module
from app.ai.faces.detector import FaceBox
from app.ai.faces.service import analyze_faces
from app.ai.faces.tracker import FaceTracker
from app.models.face_analysis import FaceAnalysis
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from tests.conftest import FAKE_MP4, auth_headers, upload


def _box(x: float, y: float = 100.0, size: float = 60.0) -> FaceBox:
    return FaceBox(x=x, y=y, w=size, h=size)


def test_tracker_keeps_stable_ids_for_small_movements() -> None:
    tracker = FaceTracker()
    first = tracker.update([_box(100.0), _box(400.0)], 640, 480)
    second = tracker.update([_box(105.0), _box(395.0)], 640, 480)
    assert sorted(pid for pid, _ in first) == [1, 2]
    assert sorted(pid for pid, _ in second) == [1, 2]
    # the left face stays person 1
    assert [pid for pid, box in second if box.cx < 320] == [1]


def test_tracker_assigns_new_id_to_distant_face() -> None:
    tracker = FaceTracker()
    tracker.update([_box(100.0)], 640, 480)
    assigned = tracker.update([_box(500.0)], 640, 480)
    assert [pid for pid, _ in assigned] == [2]


def test_tracker_retires_lost_tracks_after_max_missed() -> None:
    tracker = FaceTracker(max_missed=2)
    tracker.update([_box(100.0)], 640, 480)
    tracker.update([], 640, 480)
    tracker.update([], 640, 480)
    assert tracker.active_ids == [1]  # still within grace period
    tracker.update([], 640, 480)
    assert tracker.active_ids == []
    # a returning face gets a fresh person id
    assigned = tracker.update([_box(100.0)], 640, 480)
    assert [pid for pid, _ in assigned] == [2]


def _make_test_video(path: Path, duration: int = 6) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"testsrc=size=320x240:duration={duration}:rate=10",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(path)],
        check=True, capture_output=True,
    )


def test_analyze_faces_returns_json_result_without_faces(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    _make_test_video(video)

    result = analyze_faces(video, sample_fps=2.0)

    assert result.frames_sampled > 0
    assert result.people == []
    payload = result.to_dict()
    assert payload["people_count"] == 0
    assert payload["width"] == 320 and payload["height"] == 240
    json.dumps(payload)  # must be JSON-serializable


def _seed_face_job(db_session: Session, stored_filename: str = "stored.mp4") -> int:
    user = User(email="faces@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename=stored_filename,
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="face_detection", status="processing",
                        progress=0)
    db_session.add(job)
    db_session.commit()
    return job.id


def test_face_detection_worker_stores_analysis(db_session: Session, tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(face_detection_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(face_detection_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    job_id = _seed_face_job(db_session)

    seen: list[int] = []

    async def _progress(value: int) -> None:
        seen.append(value)

    asyncio.run(face_detection_module.run(job_id, _progress))

    analysis = db_session.scalar(select(FaceAnalysis))
    assert analysis is not None
    assert analysis.job_id == job_id
    assert analysis.result["frames_sampled"] > 0
    assert analysis.result["people_count"] == 0
    assert seen and max(seen) >= 90


def _owned_video_id(client: TestClient, headers: dict[str, str], uploads_dir: Path) -> int:
    response = upload(client, headers, "clip.mp4", FAKE_MP4, "video/mp4")
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_faces_api_analyze_queues_job_and_get_returns_analysis(
        client: TestClient, db_session: Session, uploads_dir: Path) -> None:
    headers = auth_headers(client)
    video_id = _owned_video_id(client, headers, uploads_dir)

    response = client.get(f"/api/faces/{video_id}", headers=headers)
    assert response.status_code == 404

    response = client.post(f"/api/faces/analyze/{video_id}", headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["job_type"] == "face_detection"

    db_session.add(FaceAnalysis(video_id=video_id, job_id=None,
                                result={"people_count": 1, "people": []}))
    db_session.commit()

    response = client.get(f"/api/faces/{video_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["video_id"] == video_id
    assert body["result"]["people_count"] == 1


def test_faces_api_rejects_unknown_video(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post("/api/faces/analyze/999999", headers=headers)
    assert response.status_code == 404
