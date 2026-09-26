"""Tests for the Phase 8 dubbing pipeline: speaker turns, audio engine, worker, API."""

import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.routes.dubbings as dubbings_module
import app.workers.jobs.dubbing as dubbing_module
from app.ai.dubbing.audio import assign_speakers, build_dubbed_video, synthesize_segments
from app.ai.dubbing.providers import Voice
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.user import User
from app.models.video import Video
from app.video.analyze import probe_video
from tests.conftest import FAKE_MP4, auth_headers, upload


class _FakeTTS:
    """Offline TTS stand-in: renders a short tone per segment."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
        self.calls.append((text, voice_id))
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=660:duration=0.6",
             "-c:a", "libmp3lame", str(output_path)],
            check=True, capture_output=True,
        )

    async def list_voices(self, language: str | None = None) -> list[Voice]:
        return []


def _segments() -> list[dict]:
    return [
        {"start": 0.0, "end": 1.0, "text": "hello world"},
        {"start": 1.2, "end": 2.0, "text": "second line"},
        {"start": 5.0, "end": 6.0, "text": "new speaker"},
        {"start": 6.1, "end": 7.0, "text": "  "},
    ]


def _make_test_video(path: Path, duration: int = 6) -> None:
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"testsrc=size=320x240:duration={duration}:rate=10",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(path)],
        check=True, capture_output=True,
    )


def test_assign_speakers_alternates_on_long_pauses() -> None:
    assigned = assign_speakers(_segments(), gap_threshold=1.5)
    assert [speaker for _seg, speaker in assigned] == ["A", "A", "B", "B"]


def test_synthesize_segments_skips_empty_text(tmp_path: Path) -> None:
    provider = _FakeTTS()
    assigned = assign_speakers(_segments())
    voices = {
        "A": Voice(id="voice-a", name="A", language="en", gender="F", provider="fake"),
        "B": Voice(id="voice-b", name="B", language="en", gender="M", provider="fake"),
    }
    results = asyncio.run(synthesize_segments(provider, assigned, voices, tmp_path))

    assert len(results) == 3  # the whitespace-only segment is skipped
    assert len(provider.calls) == 3
    assert provider.calls[2][1] == "voice-b"  # third segment belongs to speaker B
    for _segment, path in results:
        assert path.is_file() and path.stat().st_size > 0


def test_build_dubbed_video_mixes_timed_dubs(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    _make_test_video(source)
    dub_dir = tmp_path / "dubs"
    dub_dir.mkdir()
    provider = _FakeTTS()
    assigned = assign_speakers(_segments()[:3])
    voices = {
        "A": Voice(id="voice-a", name="A", language="en", gender="F", provider="fake"),
        "B": Voice(id="voice-b", name="B", language="en", gender="M", provider="fake"),
    }
    dubbed = asyncio.run(synthesize_segments(provider, assigned, voices, dub_dir))

    output = tmp_path / "dubbed.mp4"
    build_dubbed_video(source, dubbed, output)

    assert output.is_file() and output.stat().st_size > 0
    info = probe_video(output)
    assert info.width == 320 and info.height == 240  # video stream copied untouched
    assert any("audio" in stream for stream in _stream_types(output))
    assert info.duration == pytest.approx(6, abs=0.5)


def _stream_types(path: Path) -> list[str]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.split()


def _seed_dubbing_job(db_session: Session, stored_filename: str = "stored.mp4") -> int:
    user = User(email="dub@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename=stored_filename,
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    transcript = Transcript(video_id=video.id, language="en", full_text="hello world",
                            segments=_segments()[:3])
    db_session.add(transcript)
    job = ProcessingJob(video_id=video.id, job_type="dubbing", status="processing",
                        progress=0, params={"provider": "fake"})
    db_session.add(job)
    db_session.commit()
    return job.id


async def _fake_speaker_voices(*_args, **_kwargs) -> dict[str, Voice]:
    return {
        "A": Voice(id="voice-a", name="A", language="en", gender="F", provider="fake"),
        "B": Voice(id="voice-b", name="B", language="en", gender="M", provider="fake"),
    }


def test_dubbing_worker_produces_dubbed_video(db_session: Session, tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(dubbing_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(dubbing_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(dubbing_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(dubbing_module, "get_provider", lambda _name: _FakeTTS())
    monkeypatch.setattr(dubbing_module, "resolve_speaker_voices", _fake_speaker_voices)

    _make_test_video(uploads / "stored.mp4")
    job_id = _seed_dubbing_job(db_session)

    seen: list[int] = []

    async def _progress(value: int) -> None:
        seen.append(value)

    asyncio.run(dubbing_module.run(job_id, _progress))

    job = db_session.get(ProcessingJob, job_id)
    assert job is not None and job.output_path, "worker should record the dubbed file"
    out_file = outputs / job.output_path
    assert out_file.is_file() and out_file.stat().st_size > 0
    info = probe_video(out_file)
    assert info.width == 320 and info.height == 240
    assert seen and max(seen) >= 90


def test_dubbing_worker_requires_transcript(db_session: Session, tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(dubbing_module, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(dubbing_module, "SessionLocal", lambda: db_session)

    user = User(email="notranscript@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename="x.mp4",
                  content_type="video/mp4", size_bytes=1)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="dubbing", status="processing", progress=0)
    db_session.add(job)
    db_session.commit()

    async def _progress(_value: int) -> None:
        pass

    with pytest.raises(RuntimeError, match="Transcribe the video before dubbing"):
        asyncio.run(dubbing_module.run(job.id, _progress))


def _owned_video_id(client: TestClient, headers: dict[str, str], uploads_dir: Path) -> int:
    response = upload(client, headers, "clip.mp4", FAKE_MP4, "video/mp4")
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_start_dubbing_requires_transcript(client: TestClient, uploads_dir: Path) -> None:
    headers = auth_headers(client)
    video_id = _owned_video_id(client, headers, uploads_dir)

    response = client.post(f"/api/dubbings/start/{video_id}", json={}, headers=headers)
    assert response.status_code == 409
    assert "transcript" in response.json()["detail"].lower()


def test_start_dubbing_queues_job_with_params(client: TestClient, db_session: Session,
                                             uploads_dir: Path) -> None:
    headers = auth_headers(client)
    video_id = _owned_video_id(client, headers, uploads_dir)
    db_session.add(Transcript(video_id=video_id, language="en", full_text="hello",
                              segments=[{"start": 0.0, "end": 1.0, "text": "hello"}]))
    db_session.commit()

    response = client.post(
        f"/api/dubbings/start/{video_id}",
        json={"provider": "edge", "voice": None, "target_language": None},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_type"] == "dubbing"
    assert body["params"] == {"provider": "edge", "voice": None, "target_language": None}
    assert body["has_output"] is False


def test_dubbing_voices_and_preview_use_mocked_provider(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_voices = [Voice(id="v1", name="Test Voice", language="en", gender="F", provider="edge")]

    async def _voices(provider: str | None, language: str | None = None) -> list[Voice]:
        assert provider == "edge"
        return fake_voices

    class _PreviewTTS:
        name = "edge"

        async def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
            assert voice_id == "v1"
            output_path.write_bytes(b"FAKEMP3")

        async def list_voices(self, language: str | None = None) -> list[Voice]:
            return fake_voices

    async def _resolve(provider_name: str | None, language: str,
                       gender: str | None = None, voice_id: str | None = None) -> Voice:
        return fake_voices[0]

    monkeypatch.setattr(dubbings_module, "provider_voices", _voices)
    monkeypatch.setattr(dubbings_module, "get_provider", lambda _name: _PreviewTTS())
    monkeypatch.setattr(dubbings_module, "resolve_voice", _resolve)

    headers = auth_headers(client, email="voices@example.com")
    response = client.get("/api/dubbings/voices?provider=edge&language=en", headers=headers)
    assert response.status_code == 200
    assert response.json() == [
        {"id": "v1", "name": "Test Voice", "language": "en", "gender": "F", "provider": "edge"}
    ]

    response = client.post("/api/dubbings/preview",
                           json={"text": "hello", "voice": "v1", "provider": "edge"},
                           headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"FAKEMP3"
