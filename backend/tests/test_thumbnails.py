"""Tests for thumbnail candidate extraction, scoring, the worker, and the API."""

import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.workers.jobs.thumbnails as thumbnails_module
from app.models.processing_job import ProcessingJob
from app.models.thumbnail import Thumbnail
from app.models.user import User
from app.models.video import Video
from app.video.thumbnails import pick_candidate_timestamps, score_candidates, ScoredFrame
from tests.conftest import auth_headers


def _make_test_video(path: Path, duration: int = 6) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"testsrc=size=320x240:duration={duration}:rate=10",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(path)],
        check=True, capture_output=True,
    )


def _seed_video(db_session: Session, email: str = "thumb@example.com") -> Video:
    user = User(email=email, password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename="stored.mp4",
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    db_session.commit()
    return video


def test_pick_candidate_timestamps_spread_across_video() -> None:
    timestamps = pick_candidate_timestamps(100.0, 5)
    assert timestamps == [2.0, 26.0, 50.0, 74.0, 98.0]
    assert pick_candidate_timestamps(0, 5) == []
    assert len(pick_candidate_timestamps(60.0, 1)) == 1


def test_thumbnails_worker_extracts_and_scores(db_session: Session, tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(thumbnails_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(thumbnails_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(thumbnails_module, "THUMBNAIL_DIR", outputs / "thumbnails")
    monkeypatch.setattr(thumbnails_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    video = _seed_video(db_session)
    job = ProcessingJob(video_id=video.id, job_type="thumbnails", status="processing",
                        progress=0, params={"count": 4})
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    async def _progress(value: int) -> None:
        pass

    asyncio.run(thumbnails_module.run(job_id, _progress))

    thumbnails = db_session.scalars(
        select(Thumbnail).where(Thumbnail.video_id == video.id)
    ).all()
    assert len(thumbnails) == 4
    assert all(t.score >= 0.0 and t.score <= 1.0 for t in thumbnails)
    assert all(t.width == 320 and t.height == 240 for t in thumbnails)
    for thumbnail in thumbnails:
        assert (outputs / thumbnail.path).is_file()
    # timestamps are spread out, not clustered
    stamps = sorted(t.timestamp for t in thumbnails)
    assert stamps[-1] - stamps[0] > 2.0


def test_thumbnails_api_generate_list_select_image(client: TestClient,
                                                   db_session: Session,
                                                   tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.routes.thumbnails as thumbnails_route

    headers = auth_headers(client, email="thumbapi@example.com")
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "thumbnails").mkdir()
    monkeypatch.setattr(thumbnails_route, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(thumbnails_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(thumbnails_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(thumbnails_module, "THUMBNAIL_DIR", outputs / "thumbnails")
    monkeypatch.setattr(thumbnails_module, "SessionLocal", lambda: db_session)

    # Upload a real video through the API so ownership is wired correctly.
    _make_test_video(tmp_path / "real.mp4")
    with open(tmp_path / "real.mp4", "rb") as handle:
        response = client.post("/api/videos/upload", headers=headers,
                               files={"file": ("real.mp4", handle, "video/mp4")})
    assert response.status_code == 201, response.text
    video_id = response.json()["id"]

    # Point the worker at the uploaded file.
    from app.models.video import Video as VideoModel
    video = db_session.query(VideoModel).filter_by(id=video_id).first()
    (uploads / video.stored_filename).write_bytes((tmp_path / "real.mp4").read_bytes())

    response = client.post(f"/api/thumbnails/generate/{video_id}", headers=headers,
                           json={"count": 3})
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]

    async def _progress(value: int) -> None:
        pass

    asyncio.run(thumbnails_module.run(job_id, _progress))

    response = client.get(f"/api/thumbnails/video/{video_id}", headers=headers)
    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 3
    assert candidates[0]["score"] >= candidates[-1]["score"]  # ranked best-first
    assert not any(c["selected"] for c in candidates)

    # Preview image serves real JPEG bytes.
    first_id = candidates[0]["id"]
    response = client.get(f"/api/thumbnails/{first_id}/image", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content[:2] == b"\xff\xd8"

    # Select it as the video thumbnail.
    response = client.post(f"/api/thumbnails/{first_id}/select", headers=headers)
    assert response.status_code == 200
    assert response.json()["selected"] is True

    response = client.get(f"/api/thumbnails/video/{video_id}", headers=headers)
    selected = [c for c in response.json() if c["selected"]]
    assert len(selected) == 1 and selected[0]["id"] == first_id


def test_thumbnails_api_rejects_foreign_video(client: TestClient) -> None:
    alice = auth_headers(client, email="thumbalice@example.com")
    bob = auth_headers(client, email="thumbsob@example.com")

    response = client.post("/api/videos/upload", headers=alice,
                           files={"file": ("m.mp4", b"\x00" * 64, "video/mp4")})
    video_id = response.json()["id"]

    assert client.post(f"/api/thumbnails/generate/{video_id}", headers=bob,
                       json={}).status_code == 404
    assert client.get(f"/api/thumbnails/video/{video_id}", headers=bob).status_code == 404
