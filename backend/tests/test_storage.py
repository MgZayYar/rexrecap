"""Tests for Phase 18 object storage abstraction and remote delivery."""

import pytest
from botocore.stub import Stubber
from sqlalchemy.orm import Session

import app.workers.runner as runner_module
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from app.storage import is_remote_delivery, remote_download_url
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend


def test_local_backend_round_trip(tmp_path) -> None:
    backend = LocalStorageBackend(tmp_path / "store")
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video-bytes")
    assert not backend.exists("outputs/a.mp4")
    backend.put_file("outputs/a.mp4", src)
    assert backend.exists("outputs/a.mp4")
    backend.delete("outputs/a.mp4")
    assert not backend.exists("outputs/a.mp4")
    with pytest.raises(NotImplementedError):
        backend.presigned_get_url("outputs/a.mp4")


def test_local_backend_rejects_path_traversal(tmp_path) -> None:
    backend = LocalStorageBackend(tmp_path / "store")
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    with pytest.raises(ValueError):
        backend.put_file("../escape.mp4", src)


def _s3_backend() -> S3StorageBackend:
    return S3StorageBackend(
        bucket="rexcrop-test",
        access_key_id="test-key",
        secret_access_key="test-secret",
    )


def test_s3_presigned_url_is_signed_offline() -> None:
    backend = _s3_backend()
    url = backend.presigned_get_url("outputs/clip.mp4", expires_in=600,
                                    filename="clip.mp4")
    assert url.startswith("https://rexcrop-test.s3.amazonaws.com/outputs/clip.mp4")
    assert "Signature=" in url  # signed query-auth URL
    assert "response-content-disposition=attachment" in url


def test_s3_put_and_exists_with_stubber(tmp_path) -> None:
    backend = _s3_backend()
    stubber = Stubber(backend._client)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video-bytes")
    stubber.add_response("put_object", {})  # upload_file streams the body; skip param check
    stubber.add_response("head_object", {"ContentLength": 11}, {
        "Bucket": "rexcrop-test", "Key": "outputs/a.mp4",
    })
    stubber.add_client_error("head_object", "404", "Not Found", 404)
    with stubber:
        backend.put_file("outputs/a.mp4", src, content_type="video/mp4")
        assert backend.exists("outputs/a.mp4")
        assert not backend.exists("outputs/missing.mp4")


def test_remote_download_url_is_none_for_local_backend() -> None:
    assert not is_remote_delivery()
    assert remote_download_url("outputs/a.mp4", "a.mp4") is None
    assert remote_download_url(None, "a.mp4") is None


def _seed_job(db_session: Session, tmp_path, monkeypatch) -> ProcessingJob:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(runner_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(runner_module, "SessionLocal", lambda: db_session)
    user = User(email="storage@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    video = Video(user_id=user.id, filename="v.mp4", stored_filename="v.mp4",
                  content_type="video/mp4", size_bytes=1)
    db_session.add(video)
    db_session.flush()
    job = ProcessingJob(video_id=video.id, job_type="render", status="completed",
                        progress=100, output_path="out.mp4")
    db_session.add(job)
    db_session.commit()
    (outputs / "out.mp4").write_bytes(b"fake-video")
    return job


def test_runner_syncs_output_to_remote(db_session: Session, tmp_path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    job = _seed_job(db_session, tmp_path, monkeypatch)
    uploaded: list[tuple[str, str]] = []

    class FakeBackend:
        name = "fake"

        def put_file(self, key, path, content_type=None):
            uploaded.append((key, str(path)))

    import app.storage as storage_pkg
    monkeypatch.setattr(storage_pkg, "is_remote_delivery", lambda: True)
    monkeypatch.setattr(storage_pkg, "get_storage_backend", lambda: FakeBackend())

    runner_module._sync_output_to_remote(job.id)

    assert uploaded == [("outputs/out.mp4", str(tmp_path / "outputs" / "out.mp4"))]
    job = db_session.get(ProcessingJob, job.id)
    assert job.output_remote_key == "outputs/out.mp4"


def test_runner_sync_skipped_when_local(db_session: Session, tmp_path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    job = _seed_job(db_session, tmp_path, monkeypatch)
    runner_module._sync_output_to_remote(job.id)
    job = db_session.get(ProcessingJob, job.id)
    assert job.output_remote_key is None


def test_full_remote_delivery_chain_with_mock_s3(client, db_session: Session, tmp_path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """Seed job -> runner syncs to (mocked) S3 -> download endpoint 302s to a presigned URL."""
    import boto3
    from moto import mock_aws
    from tests.conftest import auth_headers
    import app.storage as storage_pkg

    mock = mock_aws()
    mock.start()
    monkeypatch.setattr(mock, "stop", mock.stop)  # ensure cleanup even on failure
    try:
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="rexcrop-e2e")

        monkeypatch.setattr(storage_pkg, "STORAGE_BACKEND", "s3")
        monkeypatch.setattr(storage_pkg, "S3_BUCKET", "rexcrop-e2e")
        monkeypatch.setattr(storage_pkg, "S3_REGION", "us-east-1")
        monkeypatch.setattr(storage_pkg, "S3_ACCESS_KEY_ID", "test")
        monkeypatch.setattr(storage_pkg, "S3_SECRET_ACCESS_KEY", "test")
        storage_pkg.get_storage_backend.cache_clear()

        job = _seed_job(db_session, tmp_path, monkeypatch)
        runner_module._sync_output_to_remote(job.id)
        job = db_session.get(ProcessingJob, job.id)
        assert job.output_remote_key == "outputs/out.mp4"

        backend = storage_pkg.get_storage_backend()
        assert backend.exists("outputs/out.mp4")

        headers = auth_headers(client, email="chain@example.com")
        response = client.post("/api/videos/upload", headers=headers,
                               files={"file": ("m.mp4", b"\x00" * 64, "video/mp4")})
        assert response.status_code == 201, response.text
        video_id = response.json()["id"]
        with db_session:
            video = db_session.query(Video).filter_by(id=video_id).first()
            owned = ProcessingJob(video_id=video.id, job_type="render", status="completed",
                                  progress=100, output_path="out.mp4",
                                  output_remote_key="outputs/out.mp4")
            db_session.add(owned)
            db_session.commit()
            owned_id = owned.id

        response = client.get(f"/api/jobs/{owned_id}/output", headers=headers,
                              follow_redirects=False)
        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith("https://rexcrop-e2e.s3.amazonaws.com/outputs/out.mp4")
        assert "Signature" in location
    finally:
        storage_pkg.get_storage_backend.cache_clear()
        mock.stop()


def test_job_output_download_redirects_to_remote(client, db_session: Session,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.conftest import auth_headers
    import app.api.routes.jobs as jobs_route

    headers = auth_headers(client, email="remote@example.com")
    response = client.post("/api/videos/upload", headers=headers,
                           files={"file": ("m.mp4", b"\x00" * 64, "video/mp4")})
    assert response.status_code == 201, response.text
    video_id = response.json()["id"]

    with db_session:
        video = db_session.query(Video).filter_by(id=video_id).first()
        job = ProcessingJob(video_id=video.id, job_type="render", status="completed",
                            progress=100, output_path="out.mp4",
                            output_remote_key="outputs/out.mp4")
        db_session.add(job)
        db_session.commit()
        job_id = job.id

    monkeypatch.setattr(jobs_route, "remote_download_url",
                        lambda remote_key, filename: "https://cdn.example/out.mp4")
    response = client.get(f"/api/jobs/{job_id}/output", headers=headers,
                          follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://cdn.example/out.mp4"
