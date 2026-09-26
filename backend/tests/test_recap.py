"""Tests for the recap assistant: service parsing, worker persistence, API flow."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.services.recap_assistant as recap_service
import app.workers.jobs.recap as recap_module
from app.models.processing_job import ProcessingJob
from app.models.recap_draft import RecapDraft
from app.models.transcript import Transcript
from app.models.user import User
from app.models.video import Video
from tests.conftest import auth_headers

SEGMENTS = [
    {"start": 0.0, "end": 5.0, "text": "In a quiet town, Mara finds a strange key."},
    {"start": 5.0, "end": 12.0, "text": "The key opens a door beneath the old church."},
    {"start": 12.0, "end": 20.0, "text": "Below, she discovers the town's buried secret."},
]

DRAFT_JSON = json.dumps({
    "titles": ["The Key Beneath the Church — Full Recap"],
    "hook": "One key. One buried secret. Mara is about to uncover everything.",
    "beats": [
        {"timestamp": 0.0, "heading": "The discovery",
         "summary": "Mara finds a strange key in her quiet town."},
        {"timestamp": 12.0, "heading": "The secret",
         "summary": "Beneath the church she finds what the town buried."},
    ],
    "key_quotes": [{"timestamp": 5.0, "text": "The key opens a door beneath the old church."}],
})


class _FakeResponse:
    def __init__(self, output_text: str):
        self.output_text = output_text


class _FakeResponses:
    def __init__(self, output_text: str):
        self._output_text = output_text

    def create(self, **kwargs):
        return _FakeResponse(self._output_text)


class _FakeOpenAI:
    def __init__(self, output_text: str):
        self.responses = _FakeResponses(output_text)


def _seed_video(db_session: Session, email: str, with_transcript: bool) -> Video:
    user = User(email=email, password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="clip.mp4", stored_filename="stored.mp4",
                  content_type="video/mp4", size_bytes=1234)
    db_session.add(video)
    db_session.flush()
    if with_transcript:
        db_session.add(Transcript(video_id=video.id, language="en",
                                  full_text=" ".join(s["text"] for s in SEGMENTS),
                                  segments=SEGMENTS))
    db_session.commit()
    return video


def _fake_openai_module(output_text: str):
    """A fake `openai` module whose OpenAI client returns `output_text`."""
    class _Module:
        @staticmethod
        def OpenAI(api_key=None):  # noqa: N802 - mirrors the real client name
            return _FakeOpenAI(output_text)
    return _Module()


def test_generate_recap_draft_parses_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recap_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(__import__("sys").modules, "openai", _fake_openai_module(DRAFT_JSON))
    draft = recap_service.generate_recap_draft(SEGMENTS)
    assert draft["titles"][0].startswith("The Key")
    assert len(draft["beats"]) == 2
    assert draft["beats"][0]["timestamp"] == 0.0


def test_generate_recap_draft_rejects_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recap_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(__import__("sys").modules, "openai", _fake_openai_module("not json"))
    with pytest.raises(RuntimeError, match="invalid recap draft"):
        recap_service.generate_recap_draft(SEGMENTS)


def test_generate_recap_draft_needs_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recap_service, "OPENAI_API_KEY", None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        recap_service.generate_recap_draft(SEGMENTS)


def test_recap_worker_persists_draft(db_session: Session,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recap_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(recap_module, "generate_recap_draft",
                        lambda segments: json.loads(DRAFT_JSON))

    video = _seed_video(db_session, "recapworker@example.com", with_transcript=True)
    job = ProcessingJob(video_id=video.id, job_type="recap", status="processing", progress=0)
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    async def _progress(value: int) -> None:
        pass

    asyncio.run(recap_module.run(job_id, _progress))

    draft = db_session.scalars(select(RecapDraft).where(RecapDraft.video_id == video.id)).one()
    assert draft.job_id == job_id
    assert len(draft.content["beats"]) == 2
    assert draft.model  # the model name is recorded


def test_recap_worker_fails_without_transcript(db_session: Session,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recap_module, "SessionLocal", lambda: db_session)
    video = _seed_video(db_session, "recapnotranscript@example.com", with_transcript=False)
    job = ProcessingJob(video_id=video.id, job_type="recap", status="processing", progress=0)
    db_session.add(job)
    db_session.commit()

    async def _progress(value: int) -> None:
        pass

    with pytest.raises(RuntimeError, match="no transcript"):
        asyncio.run(recap_module.run(job.id, _progress))


def test_assistant_api_flow(client: TestClient, db_session: Session,
                            monkeypatch: pytest.MonkeyPatch) -> None:
    headers = auth_headers(client, email="recapapi@example.com")
    api_user = db_session.query(User).filter_by(email="recapapi@example.com").first()
    video = _seed_video(db_session, "recapseed@example.com", with_transcript=True)
    video.user_id = api_user.id
    db_session.commit()
    video_id = video.id

    # Without a transcript the endpoint refuses before queueing.
    db_session.query(Transcript).delete()
    db_session.commit()
    response = client.post(f"/api/assistant/recap/{video_id}", headers=headers)
    assert response.status_code == 409
    db_session.add(Transcript(video_id=video_id, language="en", full_text="x",
                              segments=SEGMENTS))
    db_session.commit()

    response = client.post(f"/api/assistant/recap/{video_id}", headers=headers)
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    assert response.json()["job_type"] == "recap"

    # Simulate the worker finishing with a real draft payload.
    db_session.add(RecapDraft(video_id=video_id, job_id=job_id,
                              content=json.loads(DRAFT_JSON), model="gpt-4.1-mini"))
    db_session.commit()

    response = client.get(f"/api/assistant/recap/video/{video_id}", headers=headers)
    assert response.status_code == 200
    drafts = response.json()
    assert len(drafts) == 1
    assert drafts[0]["content"]["hook"].startswith("One key")

    response = client.get(f"/api/assistant/recap/{drafts[0]['id']}", headers=headers)
    assert response.status_code == 200

    # Another user sees nothing.
    other = auth_headers(client, email="recapother@example.com")
    assert client.get(f"/api/assistant/recap/video/{video_id}", headers=other).status_code == 404
    assert client.get(f"/api/assistant/recap/{drafts[0]['id']}", headers=other).status_code == 404
    assert client.post(f"/api/assistant/recap/{video_id}", headers=other).status_code == 404
