"""Smart crop trajectory planning from face-tracking data.

Consumes the JSON produced by the Phase 9 face detection service
(`FaceAnalysis.result`) instead of re-running detection:

- Speaker tracking: each sampled frame focuses the dominant face.
- Face priority: the largest face wins; faces closer to the camera are the
  subject of a recap shot far more often than background faces.
- Multi-speaker switching: focus switches to another face only when it is
  clearly larger (40%+) for 2 consecutive samples, so the virtual camera
  does not jitter between speakers.
- Safe margins: the dominant face is kept fully inside the crop with a
  margin on both sides; the window is clamped to the frame.
- Smooth camera movement: exponential easing toward the target plus a
  moving-average pass, so pans glide instead of jumping.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.video.analyze import VideoInfo, compute_crop_trajectory, detect_face_samples, smooth_trajectory

SWITCH_RATIO = 1.4  # challenger must be 40% larger to steal focus
SWITCH_HOLD = 2  # consecutive winning samples before the switch happens
MARGIN_RATIO = 0.08  # safe margin as a fraction of the crop width
EMA_ALPHA = 0.4  # easing factor toward the target per sample


def _area(box: dict) -> float:
    return float(box["w"]) * float(box["h"])


def plan_trajectory_from_analysis(result: dict, frame_width: int,
                                  crop_width: int) -> list[tuple[float, float]]:
    """Return [(t, crop_x)] from a FaceAnalysis result dict.

    crop_x is the left edge of the crop window, margin-safe and smoothed.
    Returns [] when the analysis contains no detections (the renderer then
    falls back to a centered crop).
    """
    by_time: dict[float, list[tuple[int, dict]]] = {}
    for person in result.get("people", []) or []:
        pid = person["person_id"]
        for detection in person.get("detections", []) or []:
            by_time.setdefault(float(detection["t"]), []).append((pid, detection))
    if not by_time:
        return []

    limit = max(0, frame_width - crop_width)
    margin = MARGIN_RATIO * crop_width

    # Speaker selection with hysteresis.
    current_id: int | None = None
    challenger_id: int | None = None
    challenger_wins = 0
    targets: list[tuple[float, dict]] = []
    for t in sorted(by_time):
        detections = sorted(by_time[t], key=lambda item: _area(item[1]), reverse=True)
        top_id, top_box = detections[0]
        if current_id is None:
            current_id = top_id
        elif top_id != current_id:
            current_box = next((box for pid, box in detections if pid == current_id), None)
            current_area = _area(current_box) if current_box else 0.0
            if current_box is None or _area(top_box) > current_area * SWITCH_RATIO:
                if challenger_id == top_id:
                    challenger_wins += 1
                else:
                    challenger_id, challenger_wins = top_id, 1
                if challenger_wins >= SWITCH_HOLD:
                    current_id, challenger_id, challenger_wins = top_id, None, 0
            else:
                challenger_id, challenger_wins = None, 0
        else:
            challenger_id, challenger_wins = None, 0
        focus_box = next((box for pid, box in detections if pid == current_id), top_box)
        targets.append((t, focus_box))

    # Margin-safe crop positions: keep the dominant face fully inside.
    raw: list[tuple[float, float]] = []
    for t, box in targets:
        face_left = float(box["x"])
        face_right = face_left + float(box["w"])
        face_cx = face_left + float(box["w"]) / 2
        x = face_cx - crop_width / 2
        low = face_right - (crop_width - margin)  # face right edge clears the margin
        high = face_left - margin  # face left edge clears the margin
        if low <= high:
            x = min(max(x, low), high)
        raw.append((t, min(max(x, 0), limit)))

    # Smooth camera movement: ease toward the target, then average.
    eased: list[float] = []
    previous = raw[0][1]
    for _, x in raw:
        previous = EMA_ALPHA * x + (1 - EMA_ALPHA) * previous
        eased.append(previous)
    smoothed = smooth_trajectory(eased, window=5)
    return [(t, x) for (t, _), x in zip(raw, smoothed)]


async def plan_crop_trajectory(video_path: Path, info: VideoInfo, crop_width: int,
                               face_result: dict | None) -> list[tuple[float, float]]:
    """Plan a crop trajectory, preferring stored face-tracking data.

    `face_result` is a FaceAnalysis result dict (or None). When it has tracked
    people, the speaker-aware planner is used; otherwise faces are detected
    live from the video. Shared by the autocrop and render workers so both
    pipelines move the virtual camera the same way.
    """
    if face_result and face_result.get("people"):
        return await asyncio.to_thread(
            plan_trajectory_from_analysis, face_result, info.width, crop_width
        )
    samples = await asyncio.to_thread(detect_face_samples, video_path)
    return compute_crop_trajectory(samples, info.width, crop_width)
