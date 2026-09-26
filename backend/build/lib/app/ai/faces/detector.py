"""Face detection with OpenCV.

Uses the Haar cascade bundled with opencv-python-headless -- no model
download needed. Wide frames are downscaled before detection for speed and
the boxes are scaled back to native coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FaceBox:
    """One detected face in native frame pixels."""

    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


_cascade = None


def _face_cascade():
    """Load the bundled frontal-face cascade once per process."""
    global _cascade
    if _cascade is None:
        import cv2

        path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(str(path))
        if cascade.empty():
            raise RuntimeError("Could not load the OpenCV face cascade")
        _cascade = cascade
    return _cascade


def detect_faces(frame_bgr, *, min_size: int = 40, max_width: int = 320) -> list[FaceBox]:
    """Detect faces in a BGR frame; returns boxes in native pixels."""
    import cv2

    height, width = frame_bgr.shape[:2]
    scale = 1.0
    if width > max_width:
        scale = max_width / width
        small = cv2.resize(frame_bgr, (max_width, int(height * scale)))
    else:
        small = frame_bgr
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    raw = _face_cascade().detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_size, min_size)
    )
    return [
        FaceBox(x=float(x) / scale, y=float(y) / scale, w=float(w) / scale, h=float(h) / scale)
        for x, y, w, h in raw
    ]
