"""Integration tests for the real autocrop worker and the job output download."""

import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.workers.jobs.autocrop as autocrop_module
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from app.video.analyze import probe_video
from tests.conftest import auth_headers


def _make_test_video(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:duration=4:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(path)],
        check=True, capture_output=True,
    )


def _seed_job(db_session: Session, stored_filename: str = "stored.mp4") -> ProcessingJob:
    user = User(email="crop@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename=stored_filename,
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="autocrop", status="processing", progress=0)
    db_session.add(job)
    db_session.commit()
    return job


def test_autocrop_worker_produces_vertical_video(db_session: Session, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(autocrop_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(autocrop_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(autocrop_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    job_id = _seed_job(db_session).id

    seen: list[int] = []

    async def _progress(value: int) -> None:
        seen.append(value)

    asyncio.run(autocrop_module.run(job_id, _progress))

    # The worker closes the shared session, so re-fetch the job row.
    job = db_session.get(ProcessingJob, job_id)
    assert job is not None and job.output_path, "worker should record the output file on the job"
    out_file = outputs / job.output_path
    assert out_file.is_file() and out_file.stat().st_size > 0
    info = probe_video(out_file)
    assert info.width / info.height == pytest.approx(9 / 16, abs=0.02)
    assert seen and max(seen) >= 90


def test_autocrop_worker_fails_cleanly_without_source_file(db_session: Session, tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(autocrop_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(autocrop_module, "SessionLocal", lambda: db_session)
    job = _seed_job(db_session, stored_filename="missing.mp4")

    async def _progress(_value: int) -> None:
        pass

    with pytest.raises(RuntimeError, match="Uploaded video file was not found"):
        asyncio.run(autocrop_module.run(job.id, _progress))


def test_download_job_output_serves_worker_file(client: TestClient, db_session: Session,
                                                tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.routes.jobs as jobs_route

    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "abc123_vertical.mp4").write_bytes(b"fake-video-bytes")
    monkeypatch.setattr(jobs_route, "OUTPUTS_DIR", outputs)

    headers = auth_headers(client)
    user = db_session.query(User).filter_by(email="user@example.com").one()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename="stored.mp4",
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="autocrop", status="completed",
                        progress=100, output_path="abc123_vertical.mp4")
    db_session.add(job)
    db_session.commit()

    response = client.get(f"/api/jobs/{job.id}/output", headers=headers)
    assert response.status_code == 200, response.text
    assert response.content == b"fake-video-bytes"


def test_download_job_output_404_without_output(client: TestClient, db_session: Session) -> None:
    headers = auth_headers(client, email="nooutput@example.com")
    user = db_session.query(User).filter_by(email="nooutput@example.com").one()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename="stored.mp4",
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="dubbing", status="completed", progress=100)
    db_session.add(job)
    db_session.commit()

    response = client.get(f"/api/jobs/{job.id}/output", headers=headers)
    assert response.status_code == 404
