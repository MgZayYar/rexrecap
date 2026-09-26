"""Face detection service: sample a video, detect and track every face.

Produces a JSON-serializable result: one entry per person with a persistent
person ID, first/last seen timestamps, and the bounding box per sampled
frame. Downstream features (smart crop, shorts) consume this instead of
re-running detection.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.ai.faces.detector import FaceBox, detect_faces
from app.ai.faces.tracker import FaceTracker
from app.video.analyze import probe_video


@dataclass
class PersonTrack:
    person_id: int
    first_seen: float = 0.0
    last_seen: float = 0.0
    detections: list[dict] = field(default_factory=list)

    def add(self, t: float, box: FaceBox) -> None:
        if not self.detections:
            self.first_seen = t
        self.last_seen = t
        self.detections.append({"t": round(t, 3), **{k: round(v, 1) for k, v in box.to_dict().items()}})

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "first_seen": round(self.first_seen, 3),
            "last_seen": round(self.last_seen, 3),
            "detection_count": len(self.detections),
            "detections": self.detections,
        }


@dataclass
class FaceAnalysisResult:
    width: int
    height: int
    duration: float
    sample_fps: float
    frames_sampled: int
    people: list[PersonTrack] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "duration": round(self.duration, 3),
            "sample_fps": self.sample_fps,
            "frames_sampled": self.frames_sampled,
            "people_count": len(self.people),
            "people": [person.to_dict() for person in self.people],
        }


def analyze_faces(video_path: Path, sample_fps: float = 2.0,
                  on_progress: Callable[[int, int], None] | None = None) -> FaceAnalysisResult:
    """Detect and track faces across sampled frames of a video file."""
    import cv2

    info = probe_video(video_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Could not open the video for face analysis")

    tracker = FaceTracker()
    people: dict[int, PersonTrack] = {}
    frames_sampled = 0
    try:
        native_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(native_fps / sample_fps)))
        total = max(1, int(info.duration * sample_fps))
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                t = index / native_fps
                boxes = detect_faces(frame)
                for person_id, box in tracker.update(boxes, info.width, info.height):
                    track = people.setdefault(person_id, PersonTrack(person_id=person_id))
                    track.add(t, box)
                frames_sampled += 1
                if on_progress:
                    on_progress(min(frames_sampled, total), total)
            index += 1
    finally:
        capture.release()

    return FaceAnalysisResult(
        width=info.width,
        height=info.height,
        duration=info.duration,
        sample_fps=sample_fps,
        frames_sampled=frames_sampled,
        people=[people[pid] for pid in sorted(people)],
    )
