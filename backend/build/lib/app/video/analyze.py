"""Video analysis for smart reframing.

Probes video metadata with ffprobe and detects faces per sampled frame with
OpenCV (Haar cascade, bundled with opencv-python-headless -- no model
download needed). Produces a smoothed horizontal crop trajectory that keeps
the subject in a vertical 9:16 frame.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import FFMPEG_BINARY

_FFPROBE_BINARY = "ffprobe"


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float


@dataclass(frozen=True)
class FaceSample:
    """One sampled frame: timestamp and face-center x coordinates (pixels)."""

    t: float
    centers_x: tuple[float, ...]


def _ffprobe_binary() -> str:
    # FFMPEG_BINARY may be "ffmpeg" or a full path; ffprobe ships alongside it.
    ffmpeg = Path(FFMPEG_BINARY)
    if ffmpeg.name == "ffmpeg":
        return _FFPROBE_BINARY
    candidate = ffmpeg.with_name("ffprobe")
    return str(candidate) if candidate.exists() else _FFPROBE_BINARY


def probe_video(video_path: Path) -> VideoInfo:
    """Read width, height, fps, and duration via ffprobe."""
    command = [
        _ffprobe_binary(),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path),
    ]
    try:
        proc = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe could not read the video: {(exc.stderr or '')[-300:]}") from exc

    payload = json.loads(proc.stdout or "{}")
    stream = (payload.get("streams") or [{}])[0]
    duration = float(stream.get("duration") or (payload.get("format") or {}).get("duration") or 0)

    num, _, den = (stream.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den) if float(den or 0) else 0.0

    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("Could not determine video dimensions")
    return VideoInfo(width=width, height=height, fps=fps, duration=duration)


def detect_face_samples(video_path: Path, sample_fps: float = 2.0) -> list[FaceSample]:
    """Sample frames at `sample_fps` and return face-center x positions per sample.

    Detection itself lives in app.ai.faces.detector so the autocrop and the
    face-analysis service share one implementation.
    """
    import cv2

    from app.ai.faces.detector import detect_faces

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Could not open the video for analysis")

    try:
        native_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(native_fps / sample_fps)))
        samples: list[FaceSample] = []
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                t = index / native_fps
                centers = tuple(box.cx for box in detect_faces(frame))
                samples.append(FaceSample(t=t, centers_x=centers))
            index += 1
    finally:
        capture.release()
    return samples


def focus_x_for_sample(sample: FaceSample, frame_width: int) -> float:
    """Horizontal focus point for one sample: mean face center, else frame center."""
    if sample.centers_x:
        return sum(sample.centers_x) / len(sample.centers_x)
    return frame_width / 2


def smooth_trajectory(values: list[float], window: int = 5) -> list[float]:
    """Centered moving average; edges use the available neighbors."""
    if window <= 1 or not values:
        return list(values)
    half = window // 2
    smoothed: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - half): i + half + 1]
        smoothed.append(sum(chunk) / len(chunk))
    return smoothed


def compute_crop_trajectory(samples: list[FaceSample], frame_width: int,
                            crop_width: int, window: int = 5) -> list[tuple[float, float]]:
    """Return [(t, crop_x)] with crop_x smoothed and clamped to the frame.

    crop_x is the left edge of the vertical crop window, chosen so the focus
    point stays centered, then clamped to [0, frame_width - crop_width].
    """
    limit = max(0, frame_width - crop_width)
    raw = [focus_x_for_sample(sample, frame_width) - crop_width / 2 for sample in samples]
    clamped = [min(max(x, 0), limit) for x in raw]
    smoothed = smooth_trajectory(clamped, window)
    return [(sample.t, x) for sample, x in zip(samples, smoothed)]
