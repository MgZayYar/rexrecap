"""Tests for Phase 10 smart auto crop: aspect ratios, speaker tracking, worker."""

import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.workers.jobs.autocrop as autocrop_module
from app.models.face_analysis import FaceAnalysis
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from app.video.analyze import probe_video
from app.video.reframe import crop_size_for_ratio
from app.video.smartcrop import plan_trajectory_from_analysis
from tests.conftest import auth_headers, upload


def _detection(t: float, x: float, size: float) -> dict:
    return {"t": t, "x": x, "y": 100.0, "w": size, "h": size}


def _result(people: list[list[dict]]) -> dict:
    return {
        "width": 1280,
        "height": 720,
        "people": [
            {"person_id": i + 1, "detections": detections}
            for i, detections in enumerate(people)
        ],
    }


def test_crop_size_for_ratio() -> None:
    assert crop_size_for_ratio(1280, 720, "9:16") == (404, 720)
    assert crop_size_for_ratio(1280, 720, "1:1") == (720, 720)
    assert crop_size_for_ratio(1280, 720, "4:5") == (576, 720)
    # Already-vertical video keeps its full frame for 9:16.
    assert crop_size_for_ratio(720, 1280, "9:16") == (720, 1280)


def test_crop_size_for_ratio_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported aspect ratio"):
        crop_size_for_ratio(1280, 720, "21:9")


def test_single_speaker_trajectory_centers_on_face() -> None:
    detections = [_detection(t / 2, x=500.0, size=120.0) for t in range(6)]
    trajectory = plan_trajectory_from_analysis(_result([detections]), 1280, 404)

    assert len(trajectory) == 6
    # Face center is 560; crop window 404 wide -> ideal x = 358.
    for _t, x in trajectory:
        assert x == pytest.approx(358.0, abs=15.0)
        assert 0 <= x <= 1280 - 404


def test_multi_speaker_switches_focus_to_larger_face() -> None:
    small = [_detection(t / 2, x=100.0, size=80.0) for t in range(6)]
    large = [_detection(t / 2, x=900.0, size=200.0) for t in range(6)]
    trajectory = plan_trajectory_from_analysis(_result([small, large]), 1280, 404)

    # Large face center is 1000 -> ideal x = 798. After the 2-sample hold the
    # camera should be heading there.
    assert trajectory[-1][1] > 600


def test_multi_speaker_hysteresis_keeps_current_speaker() -> None:
    # Person 1 is established as the speaker first; the challenger is only
    # ~20% larger in area, below the 40% switch threshold, so the camera
    # stays on person 1 instead of jittering.
    first = [_detection(t / 2, x=100.0, size=100.0) for t in range(6)]
    second = [_detection(t / 2, x=900.0, size=110.0) for t in range(3, 6)]
    trajectory = plan_trajectory_from_analysis(_result([first, second]), 1280, 404)

    # Person 1 center is 150 -> ideal x would be negative -> clamped near 0.
    assert trajectory[-1][1] < 200


def test_empty_analysis_returns_empty_trajectory() -> None:
    assert plan_trajectory_from_analysis(_result([]), 1280, 404) == []
    assert plan_trajectory_from_analysis({"people": []}, 1280, 404) == []


def _make_test_video(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:duration=4:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(path)],
        check=True, capture_output=True,
    )


def _seed_job(db_session: Session, params: dict | None,
              stored_filename: str = "stored.mp4") -> ProcessingJob:
    user = User(email="smartcrop@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename=stored_filename,
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="autocrop", status="processing",
                        progress=0, params=params)
    db_session.add(job)
    db_session.flush()
    # Stored face analysis: one person, face at x=200 (center 260 on 320-wide video).
    db_session.add(FaceAnalysis(
        video_id=video.id,
        job_id=None,
        result=_result([[_detection(t / 2, x=200.0, size=60.0) for t in range(8)]]),
    ))
    db_session.commit()
    return job


def test_autocrop_worker_uses_face_analysis_and_square_ratio(
        db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(autocrop_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(autocrop_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(autocrop_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    job = _seed_job(db_session, {"aspect_ratio": "1:1"})

    asyncio.run(autocrop_module.run(job.id, lambda value: asyncio.sleep(0)))

    job = db_session.get(ProcessingJob, job.id)
    assert job is not None and job.output_path
    assert job.output_path.endswith("_11.mp4")
    info = probe_video(outputs / job.output_path)
    assert info.width == info.height == 240  # largest 1:1 window in 320x240


def test_autocrop_worker_rejects_bad_ratio(db_session: Session, tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(autocrop_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(autocrop_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    job = _seed_job(db_session, {"aspect_ratio": "21:9"})

    async def _progress(value: int) -> None:
        pass

    with pytest.raises(RuntimeError, match="Unsupported aspect ratio"):
        asyncio.run(autocrop_module.run(job.id, _progress))


def test_jobs_create_passes_params_through(client: TestClient, db_session: Session,
                                           uploads_dir: Path) -> None:
    headers = auth_headers(client)
    response = upload(client, headers, "clip.mp4", b"fake-bytes", "video/mp4")
    assert response.status_code == 201, response.text
    video_id = response.json()["id"]

    response = client.post("/api/jobs/create", headers=headers, json={
        "video_id": video_id,
        "job_type": "autocrop",
        "params": {"aspect_ratio": "4:5"},
    })
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    job = db_session.get(ProcessingJob, job_id)
    assert job is not None
    assert job.params == {"aspect_ratio": "4:5"}
