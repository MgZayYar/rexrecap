"""Smart autocrop worker: face-aware reframe for 9:16, 1:1, and 4:5.

Pipeline: probe video -> load the stored face analysis when one exists
(else detect faces live) -> plan a speaker-tracking crop trajectory with
safe margins and smooth camera motion -> render the crop in chunks ->
record the output file on the job. When no faces are found the crop stays
centered.
"""

import asyncio
from uuid import uuid4

from sqlalchemy import select

from app.core.config import OUTPUTS_DIR, UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.face_analysis import FaceAnalysis
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.video.analyze import probe_video
from app.video.reframe import ASPECT_RATIOS, OUTPUT_SLUGS, crop_size_for_ratio, render_crop_async
from app.video.smartcrop import plan_crop_trajectory
from app.workers.jobs.simulation import ProgressReporter

DEFAULT_ASPECT_RATIO = "9:16"


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for autocrop job was not found")
        params = dict(job.params or {})
        aspect_ratio = str(params.get("aspect_ratio", DEFAULT_ASPECT_RATIO))
        if aspect_ratio not in ASPECT_RATIOS:
            raise RuntimeError(f"Unsupported aspect ratio: {aspect_ratio!r} "
                               f"(expected one of {sorted(ASPECT_RATIOS)})")
        video_id = video.id
        video_path = UPLOADS_DIR / video.stored_filename

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")

    await report_progress(5)
    info = await asyncio.to_thread(probe_video, video_path)
    await report_progress(10)

    with SessionLocal() as db:
        analysis = db.scalar(select(FaceAnalysis).where(FaceAnalysis.video_id == video_id))

    crop_size = crop_size_for_ratio(info.width, info.height, aspect_ratio)
    # Phase 9 tracking data when available; otherwise detect faces live.
    trajectory = await plan_crop_trajectory(video_path, info, crop_size[0],
                                            analysis.result if analysis else None)
    await report_progress(40)

    filename = f"{uuid4().hex}_{OUTPUT_SLUGS[aspect_ratio]}.mp4"
    output_path = OUTPUTS_DIR / filename

    loop = asyncio.get_running_loop()

    def _on_chunk(done: int, total: int) -> None:
        progress = 45 + int(45 * done / max(total, 1))
        loop.create_task(report_progress(progress))

    await render_crop_async(
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
