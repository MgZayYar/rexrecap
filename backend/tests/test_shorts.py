"""Tests for Phase 17 highlight detection and the shorts worker."""

import asyncio
import subprocess
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy.orm import Session

import app.workers.jobs.shorts as shorts_module
from app.models.processing_job import ProcessingJob
from app.models.short_clip import ShortClip
from app.models.transcript import Transcript
from app.models.user import User
from app.models.video import Video
from app.video.analyze import probe_video
from app.video.highlights import (
    audio_energy_curve,
    detect_scene_changes,
    pick_top_windows,
    score_windows,
)


def test_score_windows_prefers_loud_region() -> None:
    energy = np.concatenate([np.full(20, 0.1), np.full(20, 0.9), np.full(20, 0.1)])
    scored = score_windows(duration=30.0, energy=energy, bin_seconds=0.5,
                           scenes=[], segments=[], clip_duration=10.0, step=2.5)
    top = scored[0]
    # Loud region spans 10s..20s; the best 10s window must overlap it substantially.
    assert top["start"] < 20.0 and top["end"] > 10.0
    assert all(w["score"] <= top["score"] + 1e-9 for w in scored)


def test_score_windows_uses_speech_and_scenes() -> None:
    energy = np.full(40, 0.2)
    segments = [{"start": 14.0, "end": 19.0, "text": "dense speech here"}]
    scenes = [15.0, 15.5, 16.0, 16.5]
    scored = score_windows(duration=20.0, energy=energy, bin_seconds=0.5,
                           scenes=scenes, segments=segments,
                           clip_duration=6.0, step=1.0)
    top = scored[0]
    assert top["start"] <= 15.0 <= top["end"]


def test_pick_top_windows_has_no_overlap() -> None:
    scored = [
        {"start": 0.0, "end": 10.0, "score": 0.9},
        {"start": 5.0, "end": 15.0, "score": 0.8},
        {"start": 12.0, "end": 22.0, "score": 0.7},
        {"start": 30.0, "end": 40.0, "score": 0.6},
    ]
    picked = pick_top_windows(scored, 3)
    assert len(picked) == 3
    for i, a in enumerate(picked):
        for b in picked[i + 1:]:
            assert a["end"] <= b["start"] or b["end"] <= a["start"]
    # Sorted by start time.
    assert [w["start"] for w in picked] == sorted(w["start"] for w in picked)


def test_detect_scene_changes_finds_hard_cuts(tmp_path: Path) -> None:
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    for path, pattern in ((first, "testsrc"), (second, "smptebars")):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"{pattern}=size=160x120:duration=2:rate=10",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
            check=True, capture_output=True)
    joined = tmp_path / "joined.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:duration=2:rate=10",
         "-f", "lavfi", "-i", "smptebars=size=160x120:duration=2:rate=10",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1[out]", "-map", "[out]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(joined)],
        check=True, capture_output=True)
    cuts = detect_scene_changes(joined, threshold=0.4)
    assert any(abs(c - 2.0) < 0.5 for c in cuts), f"expected a cut near 2s, got {cuts}"


def _make_loud_middle_video(path: Path) -> None:
    """24s video; the middle 8s are much louder than the rest."""
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:duration=24:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=24",
         "-filter_complex",
         "[1:a]volume='if(between(t,8,16),4.0,0.25)':eval=frame[aloud]",
         "-map", "0:v", "-map", "[aloud]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)],
        check=True, capture_output=True)


def test_audio_energy_curve_finds_loud_middle(tmp_path: Path) -> None:
    video = tmp_path / "loud.mp4"
    _make_loud_middle_video(video)
    energy, duration = audio_energy_curve(video)
    assert duration == pytest.approx(24.0, abs=1.0)
    mid = energy[int(12 / 0.5)]
    edge = energy[int(2 / 0.5)]
    assert mid > edge * 3


_seed_counter = 0


def _seed(db_session: Session) -> tuple[ProcessingJob, str]:
    global _seed_counter
    _seed_counter += 1
    user = User(email=f"shorts{_seed_counter}@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    stored = f"shorts-{_seed_counter}.mp4"
    video = Video(user_id=user.id, filename="movie.mp4", stored_filename=stored,
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    db_session.add(Transcript(
        video_id=video.id, language="en", full_text="dialogue",
        segments=[{"start": 8.5, "end": 15.5, "text": "The big dramatic scene"}]))
    job = ProcessingJob(
        video_id=video.id, job_type="shorts", status="processing", progress=0,
        params={"count": 2, "clip_duration": 8.0, "aspect_ratio": "9:16",
                "burn_subtitles": "srt", "subtitle_source": "transcript"})
    db_session.add(job)
    db_session.commit()
    return job, stored


def _run(job_id: int) -> None:
    async def _progress(value: int) -> None:
        pass

    asyncio.run(shorts_module.run(job_id, _progress))


def test_shorts_worker_generates_vertical_clips(db_session: Session, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(shorts_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(shorts_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(shorts_module, "SessionLocal", lambda: db_session)

    job, stored = _seed(db_session)
    _make_loud_middle_video(uploads / stored)

    _run(job.id)

    job = db_session.get(ProcessingJob, job.id)
    assert job is not None and job.output_path
    clips = db_session.query(ShortClip).filter_by(job_id=job.id).order_by(ShortClip.start_time).all()
    assert len(clips) == 2
    for clip in clips:
        assert 0 <= clip.start_time < clip.end_time <= 24.5
        assert clip.end_time - clip.start_time == pytest.approx(8.0, abs=0.6)
        out_file = outputs / clip.output_path
        assert out_file.is_file() and out_file.stat().st_size > 0
        info = probe_video(out_file)
        assert info.width / info.height == pytest.approx(9 / 16, abs=0.02)
    # No overlaps between the two clips.
    assert clips[0].end_time <= clips[1].start_time
    # The loud middle section should be covered by at least one clip.
    assert any(c.start_time < 16.0 and c.end_time > 8.0 for c in clips)


def test_shorts_api_generate_and_list(client, db_session: Session) -> None:
    from tests.conftest import auth_headers
    headers = auth_headers(client, email="shortsapi@example.com")
    response = client.post("/api/videos/upload", headers=headers,
                           files={"file": ("m.mp4", b"\x00" * 64, "video/mp4")})
    assert response.status_code == 201, response.text
    video_id = response.json()["id"]
    response = client.post(f"/api/shorts/generate/{video_id}", headers=headers,
                           json={"count": 2, "clip_duration": 10})
    assert response.status_code == 201, response.text
    assert response.json()["job_type"] == "shorts"
    response = client.get(f"/api/shorts/video/{video_id}", headers=headers)
    assert response.status_code == 200
    assert response.json() == []
