"""Thumbnail candidate extraction and scoring.

Candidates are frames pulled at spread-out timestamps. Each frame is scored
by sharpness (variance of the Laplacian) plus a bonus for face prominence —
for recap thumbnails, a sharp frame with a visible face usually wins.
Scores are min-max normalized across the candidate set so they are
comparable within one video.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.video.ffmpeg import run_ffmpeg


@dataclass
class ScoredFrame:
    path: Path
    timestamp: float
    width: int
    height: int
    sharpness: float = 0.0
    face_fraction: float = 0.0
    score: float = 0.0


def pick_candidate_timestamps(duration: float, count: int = 8) -> list[float]:
    """Spread timestamps across the middle 96% of the video."""
    if duration <= 0 or count <= 0:
        return []
    start, end = duration * 0.02, duration * 0.98
    if count == 1:
        return [round((start + end) / 2, 2)]
    return [round(start + i * (end - start) / (count - 1), 2) for i in range(count)]


def extract_frame(video_path: Path, timestamp: float, output_path: Path) -> None:
    """Extract a single JPEG frame at `timestamp` seconds."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        "-y",
        "-ss", f"{timestamp:.2f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "3",
        str(output_path),
        timeout=60,
    )


def _analyze_frame(image_path: Path) -> tuple[float, float, int, int]:
    """Return (sharpness, face_area_fraction, width, height) for one frame."""
    import cv2

    frame = cv2.imread(str(image_path))
    if frame is None:
        raise ValueError(f"Could not read extracted frame {image_path}")
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    from app.ai.faces.detector import detect_faces

    faces = detect_faces(frame)
    face_area = sum(box.w * box.h for box in faces)
    face_fraction = min(1.0, face_area / (width * height)) if width * height else 0.0
    return sharpness, face_fraction, width, height


def score_candidates(frames: list[ScoredFrame]) -> list[ScoredFrame]:
    """Fill in sharpness/face stats and a normalized 0..1 score per frame."""
    for frame in frames:
        sharpness, face_fraction, width, height = _analyze_frame(frame.path)
        frame.sharpness = sharpness
        frame.face_fraction = face_fraction
        frame.width = width
        frame.height = height

    def _normalize(values: list[float]) -> list[float]:
        lo, hi = min(values), max(values)
        if hi <= lo:
            return [0.5 for _ in values]
        return [(v - lo) / (hi - lo) for v in values]

    sharp_norm = _normalize([f.sharpness for f in frames])
    # Faces dominate thumbnail choice; sharpness breaks ties.
    for frame, sharp in zip(frames, sharp_norm):
        frame.score = round(0.7 * min(1.0, frame.face_fraction * 4.0) + 0.3 * sharp, 4)
    return sorted(frames, key=lambda f: f.score, reverse=True)
