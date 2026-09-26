"""Real render worker: assemble the final delivery MP4.

Optional stages, driven by job params (all are independent and composable):

1. ``aspect_ratio`` ("9:16" | "1:1" | "4:5") -- smart-crop the source with the
   same speaker-tracking trajectory the autocrop worker uses.
2. ``burn_subtitles`` ("ass" | "srt") -- burn transcript/translation subtitles
   into the picture with FFmpeg/libass.
3. ``use_dubbed_audio`` (bool) -- replace the audio track with the video's
   latest completed dubbing output.

With no params the render is a faststart stream copy of the source. The
delivery file is ``<uuid>_render.mp4``, recorded on ``job.output_path``.

Params: {
    "aspect_ratio": "9:16" | "1:1" | "4:5" | None,
    "burn_subtitles": "ass" | "srt" | None,
    "subtitle_source": "transcript" | "translation",
    "language": str | None,
    "use_dubbed_audio": bool,
}
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import OUTPUTS_DIR, UPLOADS_DIR
from app.db.session import SessionLocal
from app.models.face_analysis import FaceAnalysis
from app.models.processing_job import ProcessingJob
from app.models.video import Video
from app.services.subtitles import resolve_subtitle_segments
from app.video.analyze import probe_video
from app.video.ffmpeg import run_ffmpeg
from app.video.reframe import ASPECT_RATIOS, crop_size_for_ratio, render_crop_async
from app.video.smartcrop import plan_crop_trajectory
from app.video.subtitles import burn_subtitles, segments_to_ass, segments_to_srt
from app.workers.jobs.simulation import ProgressReporter


def _latest_dubbing_output(db, video_id: int) -> Path | None:
    job = db.scalar(
        select(ProcessingJob)
        .where(
            ProcessingJob.video_id == video_id,
            ProcessingJob.job_type == "dubbing",
            ProcessingJob.status == "completed",
            ProcessingJob.output_path.is_not(None),
        )
        .order_by(ProcessingJob.finished_at.desc(), ProcessingJob.id.desc())
    )
    if job is None:
        return None
    path = OUTPUTS_DIR / job.output_path
    return path if path.is_file() else None


def _mux_dubbed_audio(video_path: Path, dubbed_path: Path, output_path: Path) -> None:
    """Replace the video's audio track with the dubbing output's audio."""
    run_ffmpeg(
        "-y",
        "-i", str(video_path),
        "-i", str(dubbed_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
        timeout=600,
    )


async def run(job_id: int, report_progress: ProgressReporter) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video is None:
            raise RuntimeError("Video for render job was not found")
        params = dict(job.params or {})
        aspect_ratio = params.get("aspect_ratio")
        burn_format = params.get("burn_subtitles")
        subtitle_source = str(params.get("subtitle_source", "transcript"))
        language = params.get("language")
        use_dubbed_audio = bool(params.get("use_dubbed_audio"))
        if aspect_ratio is not None and aspect_ratio not in ASPECT_RATIOS:
            raise RuntimeError(f"Unsupported aspect ratio: {aspect_ratio!r} "
                               f"(expected one of {sorted(ASPECT_RATIOS)})")
        if burn_format is not None and burn_format not in ("ass", "srt"):
            raise RuntimeError(f"Unsupported subtitle format: {burn_format!r}")
        video_id = video.id
        video_path = UPLOADS_DIR / video.stored_filename

    if not video_path.is_file():
        raise RuntimeError("Uploaded video file was not found")

    await report_progress(5)
    info = await asyncio.to_thread(probe_video, video_path)
    loop = asyncio.get_running_loop()

    with tempfile.TemporaryDirectory(prefix="rexcrop-render-") as tmp:
        tmpdir = Path(tmp)
        work = video_path

        if aspect_ratio is not None:
            with SessionLocal() as db:
                analysis = db.scalar(
                    select(FaceAnalysis).where(FaceAnalysis.video_id == video_id))
            crop_size = crop_size_for_ratio(info.width, info.height, aspect_ratio)
            trajectory = await plan_crop_trajectory(
                video_path, info, crop_size[0], analysis.result if analysis else None)
            await report_progress(10)

            def _on_chunk(done: int, total: int) -> None:
                progress = 10 + int(30 * done / max(total, 1))
                loop.create_task(report_progress(progress))

            cropped = tmpdir / "cropped.mp4"
            await render_crop_async(video_path, cropped, trajectory, crop_size,
                                    info.duration, on_chunk=_on_chunk)
            work = cropped

        if burn_format is not None:
            with SessionLocal() as db:
                segments = resolve_subtitle_segments(db, video_id, subtitle_source, language)
            if not segments:
                raise RuntimeError(
                    "No transcript available for subtitle burn" if subtitle_source == "transcript"
                    else "No translation available for subtitle burn")
            await report_progress(45)
            subtitle_text = (segments_to_ass(segments) if burn_format == "ass"
                             else segments_to_srt(segments))
            burned = tmpdir / "burned.mp4"
            await asyncio.to_thread(burn_subtitles, work, burned, subtitle_text, burn_format)
            work = burned
            await report_progress(70)

        if use_dubbed_audio:
            with SessionLocal() as db:
                dubbed_path = _latest_dubbing_output(db, video_id)
            if dubbed_path is None:
                raise RuntimeError("No completed dubbing output found for this video")
            await report_progress(75)
            muxed = tmpdir / "muxed.mp4"
            await asyncio.to_thread(_mux_dubbed_audio, work, dubbed_path, muxed)
            work = muxed
            await report_progress(88)

        filename = f"{uuid4().hex}_render.mp4"
        output_path = OUTPUTS_DIR / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if work == video_path:
            # No transformation stages: faststart stream copy.
            await asyncio.to_thread(
                run_ffmpeg, "-y", "-i", str(video_path),
                "-c", "copy", "-movflags", "+faststart", str(output_path), timeout=600)
        else:
            await asyncio.to_thread(shutil.copyfile, work, output_path)

    await report_progress(92)
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            raise RuntimeError("Render job was not found")
        job.output_path = filename
        db.commit()
    await report_progress(95)
