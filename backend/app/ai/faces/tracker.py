"""Centroid-based multi-face tracker.

Assigns a persistent person ID to each face across frames: every frame's
detections are matched greedily to existing tracks by centroid distance
(relative to the frame diagonal). Unmatched detections start new tracks;
tracks unseen for `max_missed` consecutive frames are retired.

This is deliberately simple and deterministic. ID switches can happen when
faces cross or leave the frame for a while -- a documented v1 limitation,
not a bug.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.ai.faces.detector import FaceBox


@dataclass
class Track:
    person_id: int
    box: FaceBox
    missed: int = 0


@dataclass
class FaceTracker:
    """Greedy centroid tracker over face bounding boxes."""

    max_distance: float = 0.08  # fraction of the frame diagonal
    max_missed: int = 5  # frames before a lost track is retired
    _tracks: list[Track] = field(default_factory=list, repr=False)
    _next_id: int = field(default=1, repr=False)

    def update(self, detections: list[FaceBox], frame_width: int,
               frame_height: int) -> list[tuple[int, FaceBox]]:
        """Match detections to tracks; returns [(person_id, box)]."""
        diagonal = math.hypot(frame_width, frame_height)
        limit = self.max_distance * diagonal

        unmatched = list(detections)
        assignments: list[tuple[int, FaceBox]] = []

        for track in sorted(self._tracks, key=lambda t: t.person_id):
            best_index: int | None = None
            best_distance = limit
            tx, ty = track.box.cx, track.box.cy
            for i, box in enumerate(unmatched):
                distance = math.hypot(box.cx - tx, box.cy - ty)
                if distance < best_distance:
                    best_distance = distance
                    best_index = i
            if best_index is None:
                track.missed += 1
                continue
            box = unmatched.pop(best_index)
            track.box = box
            track.missed = 0
            assignments.append((track.person_id, box))

        for box in unmatched:
            person_id = self._next_id
            self._next_id += 1
            self._tracks.append(Track(person_id=person_id, box=box))
            assignments.append((person_id, box))

        self._tracks = [t for t in self._tracks if t.missed <= self.max_missed]
        return assignments

    @property
    def active_ids(self) -> list[int]:
        return sorted(t.person_id for t in self._tracks)
