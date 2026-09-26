"""Tests for Phase 12 real render worker: crop + subtitles + dubbed audio."""

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

import app.workers.jobs.render as render_module
from app.models.face_analysis import FaceAnalysis
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.user import User
from app.models.video import Video
from app.video.analyze import probe_video

SEGMENTS = [
    {"start": 0.5, "end": 2.0, "text": "Hello world"},
    {"start": 2.5, "end": 3.5, "text": "Second line"},
]


def _make_test_video(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:duration=4:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(path)],
        check=True, capture_output=True,
    )


def _det(t: float, x: float, size: float) -> dict:
    return {"t": t, "x": x, "y": 100.0, "w": size, "h": size}


_seed_counter = 0


def _seed(db_session: Session, params: dict | None, with_dubbing: bool = False,
          stored_filename: str | None = None) -> tuple[ProcessingJob, str]:
    global _seed_counter
    _seed_counter += 1
    if stored_filename is None:
        stored_filename = f"stored-{_seed_counter}.mp4"
    user = User(email=f"render{_seed_counter}@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename=stored_filename,
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    db_session.add(Transcript(video_id=video.id, language="en", full_text="Hello world",
                              segments=SEGMENTS))
    db_session.add(FaceAnalysis(
        video_id=video.id, job_id=None,
        result={"people": [{"person_id": 1,
                            "detections": [_det(t / 2, x=200.0, size=60.0) for t in range(8)]}]},
    ))
    job = ProcessingJob(video_id=video.id, job_type="render", status="processing",
                        progress=0, params=params)
    db_session.add(job)
    db_session.flush()
    dubbed_path = None
    if with_dubbing:
        dubbed = ProcessingJob(video_id=video.id, job_type="dubbing", status="completed",
                               progress=100, output_path="dubbed.mp4")
        db_session.add(dubbed)
    db_session.commit()
    return job, stored_filename


def _run(job_id: int) -> None:
    async def _progress(value: int) -> None:
        pass

    asyncio.run(render_module.run(job_id, _progress))


def _has_audio(path: Path) -> bool:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return "audio" in proc.stdout


def test_render_worker_full_pipeline(db_session: Session, tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(render_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(render_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(render_module, "SessionLocal", lambda: db_session)

    job, stored = _seed(db_session, {
        "aspect_ratio": "9:16",
        "burn_subtitles": "ass",
        "subtitle_source": "transcript",
        "use_dubbed_audio": True,
    }, with_dubbing=True)
    _make_test_video(uploads / stored)
    shutil.copyfile(uploads / stored, outputs / "dubbed.mp4")

    _run(job.id)

    job = db_session.get(ProcessingJob, job.id)
    assert job is not None and job.output_path
    assert job.output_path.endswith("_render.mp4")
    out_file = outputs / job.output_path
    assert out_file.is_file() and out_file.stat().st_size > 0
    info = probe_video(out_file)
    assert info.width / info.height == pytest.approx(9 / 16, abs=0.02)
    assert info.duration == pytest.approx(4.0, abs=0.5)
    assert _has_audio(out_file)


def test_render_worker_noop_is_stream_copy(db_session: Session, tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(render_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(render_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(render_module, "SessionLocal", lambda: db_session)

    job, stored = _seed(db_session, None)
    _make_test_video(uploads / stored)

    _run(job.id)

    job = db_session.get(ProcessingJob, job.id)
    assert job is not None and job.output_path
    info = probe_video(outputs / job.output_path)
    assert (info.width, info.height) == (320, 240)


def test_render_worker_rejects_bad_params(db_session: Session, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(render_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(render_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(render_module, "SessionLocal", lambda: db_session)

    job, stored = _seed(db_session, {"aspect_ratio": "21:9"})
    _make_test_video(uploads / stored)
    with pytest.raises(RuntimeError, match="Unsupported aspect ratio"):
        _run(job.id)

    job, stored = _seed(db_session, {"use_dubbed_audio": True})
    _make_test_video(uploads / stored)
    with pytest.raises(RuntimeError, match="No completed dubbing"):
        _run(job.id)


def test_render_worker_requires_subtitles(db_session: Session, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(render_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(render_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(render_module, "SessionLocal", lambda: db_session)

    _make_test_video(uploads / "stored.mp4")
    user = User(email="norender@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename="stored.mp4",
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="render", status="processing",
                        progress=0, params={"burn_subtitles": "srt"})
    db_session.add(job)
    db_session.commit()
    _make_test_video(uploads / "stored.mp4")

    with pytest.raises(RuntimeError, match="No transcript"):
        _run(job.id)
