"""Tests for Phase 11 subtitle burn: serialization, worker, and API."""

import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.workers.jobs.subtitle_burn as burn_module
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.user import User
from app.models.video import Video
from app.video.analyze import probe_video
from app.video.subtitles import burn_subtitles, segments_to_ass, segments_to_srt
from tests.conftest import FAKE_MP4, auth_headers, upload

SEGMENTS = [
    {"start": 0.5, "end": 2.0, "text": "Hello world"},
    {"start": 2.5, "end": 4.25, "text": "Second line\nhere"},
]


def test_segments_to_srt() -> None:
    srt = segments_to_srt(SEGMENTS)
    assert srt.startswith("1\n00:00:00,500 --> 00:00:02,000\nHello world\n\n2\n")
    assert "00:00:02,500 --> 00:00:04,250\nSecond line\nhere\n" in srt


def test_segments_to_srt_empty() -> None:
    assert segments_to_srt([]) == ""


def test_segments_to_ass() -> None:
    ass = segments_to_ass(SEGMENTS)
    assert "Style: RexCrop,Noto Sans" in ass
    assert "Dialogue: 0,0:00:00.50,0:00:02.00,RexCrop,,0,0,0,,Hello world" in ass
    # ASS uses \N for line breaks.
    assert "Second line\\Nhere" in ass


def test_burn_subtitles_rejects_bad_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported subtitle format"):
        burn_subtitles(tmp_path / "in.mp4", tmp_path / "out.mp4", "text", "vtt")
    with pytest.raises(ValueError, match="empty subtitles"):
        burn_subtitles(tmp_path / "in.mp4", tmp_path / "out.mp4", "   ", "srt")


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
    user = User(email="burn@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename=stored_filename,
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    db_session.add(Transcript(video_id=video.id, language="en", full_text="Hello world",
                              segments=SEGMENTS))
    job = ProcessingJob(video_id=video.id, job_type="subtitle_burn", status="processing",
                        progress=0, params=params)
    db_session.add(job)
    db_session.commit()
    return job


def test_subtitle_burn_worker_produces_video(db_session: Session, tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(burn_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(burn_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(burn_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    job = _seed_job(db_session, {"source": "transcript", "format": "ass"})

    seen: list[int] = []

    async def _progress(value: int) -> None:
        seen.append(value)

    asyncio.run(burn_module.run(job.id, _progress))

    job = db_session.get(ProcessingJob, job.id)
    assert job is not None and job.output_path
    assert job.output_path.endswith("_subtitled.mp4")
    out_file = outputs / job.output_path
    assert out_file.is_file() and out_file.stat().st_size > 0
    info = probe_video(out_file)
    assert info.duration == pytest.approx(4.0, abs=0.5)
    assert (info.width, info.height) == (320, 240)
    assert seen and max(seen) >= 90


def test_subtitle_burn_worker_fails_without_transcript(db_session: Session, tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(burn_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(burn_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    user = User(email="notranscript@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename="stored.mp4",
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="subtitle_burn", status="processing",
                        progress=0, params={"source": "transcript", "format": "srt"})
    db_session.add(job)
    db_session.commit()

    async def _progress(value: int) -> None:
        pass

    with pytest.raises(RuntimeError, match="No transcript"):
        asyncio.run(burn_module.run(job.id, _progress))


def _owned_video_id(client: TestClient, headers: dict[str, str]) -> int:
    response = upload(client, headers, "clip.mp4", FAKE_MP4, "video/mp4")
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_subtitles_burn_api(client: TestClient, db_session: Session, uploads_dir: Path) -> None:
    headers = auth_headers(client)
    video_id = _owned_video_id(client, headers)

    # No transcript yet -> 409.
    response = client.post(f"/api/subtitles/burn/{video_id}", headers=headers, json={})
    assert response.status_code == 409

    db_session.add(Transcript(video_id=video_id, language="en", full_text="Hello",
                              segments=SEGMENTS))
    db_session.commit()

    response = client.post(f"/api/subtitles/burn/{video_id}", headers=headers, json={
        "source": "transcript", "format": "srt",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_type"] == "subtitle_burn"

    # Translation requested but missing -> 409.
    response = client.post(f"/api/subtitles/burn/{video_id}", headers=headers, json={
        "source": "translation", "format": "ass", "language": "es",
    })
    assert response.status_code == 409

    # Unknown video -> 404.
    response = client.post("/api/subtitles/burn/999999", headers=headers, json={})
    assert response.status_code == 404
