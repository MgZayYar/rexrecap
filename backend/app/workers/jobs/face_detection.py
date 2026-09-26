"""Face detection worker.

Pipeline: load job + video -> sample frames at ~2 fps -> detect faces with
the OpenCV Haar cascade -> track them across frames with persistent person
IDs -> store the JSON result as the video's FaceAnalysis (replacing any
previous analysis).
"""

import asyncio

from sqlalchemy import select

from app.ai.faces.service import analyze_faces
from app.core.config import UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.face_analysis import FaceAnalysis
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.workers.jobs.simulation import ProgressReporter


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for face detection job was not found")
        params = dict(job.params or {})
        sample_fps = float(params.get("sample_fps", 2.0))
        video_path = UPLOADS_DIR / video.stored_filename
        video_id = video.id

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")

    await report_progress(5)
    loop = asyncio.get_running_loop()

    def _on_progress(done: int, total: int) -> None:
        progress = 5 + int(85 * done / max(total, 1))
        loop.create_task(report_progress(progress))

    result = await asyncio.to_thread(analyze_faces, video_path, sample_fps, _on_progress)
    await report_progress(92)

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            raise RuntimeError("Face detection job was not found")
        existing = db.scalar(select(FaceAnalysis).where(FaceAnalysis.video_id == video_id))
        if existing is not None:
            db.delete(existing)
            db.flush()
        db.add(FaceAnalysis(video_id=video_id, job_id=job.id, result=result.to_dict()))
        db.commit()
    await report_progress(95)
