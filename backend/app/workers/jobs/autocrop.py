"""Real autocrop worker: vertical 9:16 reframe with face-aware tracking.

Pipeline: probe video -> sample frames and detect faces -> build a smoothed
horizontal crop trajectory -> render the vertical crop in chunks -> record the
output file on the job. When no faces are found the crop stays centered.
"""

import asyncio
from uuid import uuid4

from app.core.config import OUTPUTS_DIR, UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.video.analyze import compute_crop_trajectory, detect_face_samples, probe_video
from app.video.reframe import render_vertical_async, vertical_crop_size
from app.workers.jobs.simulation import ProgressReporter


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for autocrop job was not found")
        video_path = UPLOADS_DIR / video.stored_filename

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")

    await report_progress(5)
    info = await asyncio.to_thread(probe_video, video_path)
    await report_progress(10)
    samples = await asyncio.to_thread(detect_face_samples, video_path)
    await report_progress(40)

    crop_size = vertical_crop_size(info.width, info.height)
    trajectory = compute_crop_trajectory(samples, info.width, crop_size[0])

    filename = f"{uuid4().hex}_vertical.mp4"
    output_path = OUTPUTS_DIR / filename

    loop = asyncio.get_running_loop()

    def _on_chunk(done: int, total: int) -> None:
        progress = 45 + int(45 * done / max(total, 1))
        loop.create_task(report_progress(progress))

    await render_vertical_async(
        video_path, output_path, trajectory, crop_size, info.duration,
        on_chunk=_on_chunk,
    )
    await report_progress(92)

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            raise RuntimeError("Autocrop job was not found")
        job.output_path = filename
        db.commit()
    await report_progress(95)
