"""Tests for job-event notifications: email (SMTP), webhooks, and the settings API."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.services.notifications as notifications
import app.workers.runner as runner_module
from app.models.notification_setting import NotificationSetting
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from tests.conftest import auth_headers


def _seed_user_video_job(db_session: Session) -> tuple[int, int, int]:
    user = User(email="notify@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="movie.mp4", stored_filename="abc.mp4",
                  content_type="video/mp4", size_bytes=1024, status="ready")
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="render", status="completed",
                        progress=100,
                        finished_at=datetime.now(timezone.utc))
    db_session.add(job)
    db_session.commit()
    return user.id, video.id, job.id


def _add_setting(db_session: Session, user_id: int, channel="email",
                 target="me@example.com",
                 events=("job_completed",), enabled=True) -> NotificationSetting:
    setting = NotificationSetting(user_id=user_id, channel=channel, target=target,
                                  events=list(events), enabled=enabled)
    db_session.add(setting)
    db_session.commit()
    return setting


def test_dispatch_sends_email_via_smtp(db_session: Session,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, _, job_id = _seed_user_video_job(db_session)
    _add_setting(db_session, user_id)

    sent = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(notifications, "SessionLocal", lambda: db_session)

    notifications.dispatch_job_notifications(job_id)

    assert len(sent) == 1
    assert sent[0]["To"] == "me@example.com"
    assert "completed" in sent[0]["Subject"]


def test_dispatch_sends_webhook(db_session: Session,
                                monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, video_id, job_id = _seed_user_video_job(db_session)
    _add_setting(db_session, user_id, channel="webhook",
                 target="https://hooks.example/notify")

    posted = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

    def fake_post(url, json=None, timeout=None, headers=None):
        posted.append((url, json, headers))
        return FakeResponse()

    monkeypatch.setattr(notifications.httpx, "post", fake_post)
    monkeypatch.setattr(notifications, "SessionLocal", lambda: db_session)

    notifications.dispatch_job_notifications(job_id)

    assert len(posted) == 1
    url, payload, headers = posted[0]
    assert url == "https://hooks.example/notify"
    assert payload["event"] == "job_completed"
    assert payload["job_id"] == job_id
    assert payload["video_filename"] == "movie.mp4"
    assert headers["X-RexCrop-Event"] == "job_completed"


def test_dispatch_respects_enabled_and_event_filter(db_session: Session,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, _, job_id = _seed_user_video_job(db_session)
    _add_setting(db_session, user_id, channel="webhook",
                 target="https://hooks.example/disabled",
                 events=("job_completed",), enabled=False)
    _add_setting(db_session, user_id, channel="webhook",
                 target="https://hooks.example/wrong-event",
                 events=("job_failed",), enabled=True)

    posted = []
    monkeypatch.setattr(
        notifications.httpx, "post",
        lambda *a, **k: posted.append(a) or type("R", (), {
            "status_code": 200, "raise_for_status": lambda self: None})())
    monkeypatch.setattr(notifications, "SessionLocal", lambda: db_session)

    notifications.dispatch_job_notifications(job_id)

    assert posted == []


def test_dispatch_never_raises_on_send_failure(db_session: Session,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, _, job_id = _seed_user_video_job(db_session)
    _add_setting(db_session, user_id, channel="webhook",
                 target="https://hooks.example/boom")

    def boom(*args, **kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(notifications.httpx, "post", boom)
    monkeypatch.setattr(notifications, "SessionLocal", lambda: db_session)

    # Must not raise; failures are only logged.
    notifications.dispatch_job_notifications(job_id)


def test_dispatch_without_smtp_config_skips_email(db_session: Session,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, _, job_id = _seed_user_video_job(db_session)
    _add_setting(db_session, user_id)

    monkeypatch.setattr(notifications, "SMTP_HOST", "")
    monkeypatch.setattr(notifications, "SessionLocal", lambda: db_session)

    # No SMTP configured: skipped gracefully, no exception.
    notifications.dispatch_job_notifications(job_id)


def test_runner_notifies_on_failed_job(monkeypatch: pytest.MonkeyPatch) -> None:
    notified = []
    monkeypatch.setattr(runner_module, "_notify_job_finished",
                        lambda job_id: notified.append(job_id) or _coro())
    monkeypatch.setattr(runner_module, "JOB_HANDLERS",
                        {"boom": lambda job_id, progress: _raise()})
    monkeypatch.setattr(runner_module, "_cancel_requested", lambda job_id: False)
    monkeypatch.setattr(runner_module, "_report_progress", lambda *a: None)

    class FakeSession:
        def __init__(self):
            self.job = type("J", (), {"id": 1, "status": "processing",
                                      "error_message": None, "finished_at": None})()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, model, job_id):
            return self.job

        def commit(self):
            pass

    monkeypatch.setattr(runner_module, "SessionLocal", FakeSession)

    import asyncio
    asyncio.run(runner_module.process_claimed_job(1, "boom"))
    assert notified == [1]


def _coro():
    async def _noop():
        return None
    return _noop()


def _raise():
    raise RuntimeError("handler exploded")


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

def test_notification_settings_crud(client: TestClient, db_session: Session) -> None:
    headers = auth_headers(client, email="settings@example.com")

    response = client.get("/api/notifications/settings", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

    response = client.post("/api/notifications/settings", headers=headers, json={
        "channel": "email", "target": "me@example.com",
        "events": ["job_completed", "job_failed"], "enabled": True})
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["channel"] == "email"
    assert created["target"] == "me@example.com"

    response = client.patch(f"/api/notifications/settings/{created['id']}",
                            headers=headers, json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    response = client.delete(f"/api/notifications/settings/{created['id']}",
                             headers=headers)
    assert response.status_code == 204

    response = client.get("/api/notifications/settings", headers=headers)
    assert response.json() == []


def test_notification_settings_validation(client: TestClient) -> None:
    headers = auth_headers(client, email="validate@example.com")

    # bad email target
    response = client.post("/api/notifications/settings", headers=headers, json={
        "channel": "email", "target": "not-an-email"})
    assert response.status_code == 422

    # bad webhook URL
    response = client.post("/api/notifications/settings", headers=headers, json={
        "channel": "webhook", "target": "ftp://example.com/hook"})
    assert response.status_code == 422

    # unknown event
    response = client.post("/api/notifications/settings", headers=headers, json={
        "channel": "webhook", "target": "https://example.com/hook",
        "events": ["job_exploded"]})
    assert response.status_code == 422

    # bad channel
    response = client.post("/api/notifications/settings", headers=headers, json={
        "channel": "sms", "target": "+15551234567"})
    assert response.status_code == 422


def test_notification_settings_are_user_scoped(client: TestClient) -> None:
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com")

    response = client.post("/api/notifications/settings", headers=alice, json={
        "channel": "webhook", "target": "https://example.com/hook"})
    setting_id = response.json()["id"]

    # Bob cannot see, modify, or delete Alice's setting.
    assert client.get("/api/notifications/settings", headers=bob).json() == []
    assert client.patch(f"/api/notifications/settings/{setting_id}",
                        headers=bob, json={"enabled": False}).status_code == 404
    assert client.delete(f"/api/notifications/settings/{setting_id}",
                         headers=bob).status_code == 404


def test_notification_test_endpoint(client: TestClient, db_session: Session,
                                    monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.routes.notifications as notifications_route

    headers = auth_headers(client, email="testping@example.com")
    response = client.post("/api/notifications/settings", headers=headers, json={
        "channel": "webhook", "target": "https://example.com/hook"})
    setting_id = response.json()["id"]

    monkeypatch.setattr(notifications, "SessionLocal", lambda: db_session)
    delivered = []
    monkeypatch.setattr(
        notifications, "httpx",
        type("H", (), {"post": staticmethod(
            lambda *a, **k: delivered.append(a) or type("R", (), {
                "status_code": 200,
                "raise_for_status": lambda self: None})())}))

    response = client.post(f"/api/notifications/settings/{setting_id}/test",
                           headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}
    assert delivered
