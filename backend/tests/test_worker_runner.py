"""Tests for Phase 14: the standalone DB-backed worker process."""

import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.workers.runner as runner
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.video import Video


@pytest.fixture()
def runner_db(monkeypatch: pytest.MonkeyPatch):
    """Point the runner at an isolated temp database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    from app.db.base import Base
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, "SessionLocal", factory)
    try:
        yield factory
    finally:
        engine.dispose()
        os.unlink(path)


_seed_counter = 0


def _seed_job(factory, job_type: str = "render", status: str = "queued") -> int:
    global _seed_counter
    _seed_counter += 1
    with factory() as db:
        user = User(email=f"worker{_seed_counter}@example.com", password_hash="x")
        db.add(user)
        db.flush()
        video = Video(user_id=user.id, filename="c.mp4",
                      stored_filename=f"c{_seed_counter}.mp4",
                      content_type="video/mp4", size_bytes=1)
        db.add(video)
        db.flush()
        job = ProcessingJob(video_id=video.id, job_type=job_type, status=status, progress=0)
        db.add(job)
        db.commit()
        return job.id


def _get_job(factory, job_id: int) -> ProcessingJob:
    with factory() as db:
        return db.get(ProcessingJob, job_id)


def test_claim_next_job_takes_oldest_queued(runner_db) -> None:
    first = _seed_job(runner_db)
    second = _seed_job(runner_db)
    claimed = runner.claim_next_job()
    assert claimed == (first, "render")
    assert _get_job(runner_db, first).status == "processing"
    assert _get_job(runner_db, second).status == "queued"


def test_claim_next_job_empty_returns_none(runner_db) -> None:
    assert runner.claim_next_job() is None


def test_concurrent_claims_never_double_process(runner_db) -> None:
    ids = {_seed_job(runner_db) for _ in range(4)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = [future.result() for future in
                   [pool.submit(runner.claim_next_job) for _ in range(8)]]
    claimed_ids = [c[0] for c in claimed if c is not None]
    assert sorted(claimed_ids) == sorted(ids)
    assert runner.claim_next_job() is None


def test_run_once_processes_job(runner_db, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []

    async def fake_handler(job_id: int, report_progress) -> None:
        seen.append(job_id)
        await report_progress(42)
        with runner_db() as db:
            job = db.get(ProcessingJob, job_id)
            assert job.progress == 42

    monkeypatch.setitem(runner.JOB_HANDLERS, "render", fake_handler)
    job_id = _seed_job(runner_db)
    assert asyncio.run(runner.run_once()) is True
    assert seen == [job_id]
    job = _get_job(runner_db, job_id)
    assert job.status == "completed"
    assert job.progress == 100
    assert job.finished_at is not None


def test_run_once_marks_failed_jobs(runner_db, monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_handler(job_id: int, report_progress) -> None:
        raise RuntimeError("boom")

    monkeypatch.setitem(runner.JOB_HANDLERS, "render", failing_handler)
    job_id = _seed_job(runner_db)
    assert asyncio.run(runner.run_once()) is True
    job = _get_job(runner_db, job_id)
    assert job.status == "failed"
    assert job.error_message == "boom"
    assert job.finished_at is not None


def test_run_once_empty_queue_returns_false(runner_db) -> None:
    assert asyncio.run(runner.run_once()) is False


def test_unknown_job_type_fails_job(runner_db) -> None:
    job_id = _seed_job(runner_db, job_type="nope")
    assert asyncio.run(runner.run_once()) is True
    job = _get_job(runner_db, job_id)
    assert job.status == "failed"
    assert "nope" in job.error_message


def test_recover_interrupted_jobs(runner_db) -> None:
    interrupted = _seed_job(runner_db, status="processing")
    assert runner.recover_interrupted_jobs() == 1
    job = _get_job(runner_db, interrupted)
    assert job.status == "queued"
    assert job.progress == 0
    assert runner.recover_interrupted_jobs() == 0


def test_run_forever_recovers_and_processes_until_stopped(runner_db,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    processed: list[int] = []

    async def fake_handler(job_id: int, report_progress) -> None:
        processed.append(job_id)

    monkeypatch.setitem(runner.JOB_HANDLERS, "render", fake_handler)
    monkeypatch.setattr(runner, "WORKER_POLL_INTERVAL", 0.05)
    interrupted = _seed_job(runner_db, status="processing")
    fresh = _seed_job(runner_db)

    async def _drive() -> None:
        stop_event = asyncio.Event()

        async def _watch() -> None:
            for _ in range(200):
                with runner_db() as db:
                    done = all(
                        db.get(ProcessingJob, job_id).status == "completed"
                        for job_id in (interrupted, fresh)
                    )
                if done:
                    stop_event.set()
                    return
                await asyncio.sleep(0.05)
            raise TimeoutError("worker did not finish both jobs")

        await asyncio.gather(runner.run_forever(stop_event), _watch())

    asyncio.run(_drive())
    assert sorted(processed) == sorted([interrupted, fresh])
