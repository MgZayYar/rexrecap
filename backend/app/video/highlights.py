"""Highlight moment detection for shorts generation.

A "highlight" is a time window that scores highly on a blend of three
signals, all computed locally with ffmpeg/numpy:

- audio energy: RMS loudness per time bin (exciting moments are loud),
- scene-change density: lots of cuts (action, montages),
- speech coverage: fraction of the window covered by transcript segments.

Windows are scored on a sliding grid and the top-N non-overlapping ones
are returned as clip candidates.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from app.core.config import FFMPEG_BINARY

_BIN_SECONDS = 0.5
_SCENE_RE = re.compile(r"pts_time:([0-9.]+)")


def audio_energy_curve(video_path: Path, bin_seconds: float = _BIN_SECONDS) -> tuple[np.ndarray, float]:
    """Return (rms_energy_per_bin, duration_seconds) for the video's audio.

    Returns an empty curve and 0.0 duration when the video has no audio.
    """
    with tempfile.TemporaryDirectory(prefix="rexcrop-energy-") as tmp:
        wav = Path(tmp) / "audio.wav"
        result = subprocess.run(
            [FFMPEG_BINARY, "-y", "-v", "error", "-i", str(video_path),
             "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
            capture_output=True)
        if result.returncode != 0 or not wav.is_file():
            return np.zeros(0, dtype=np.float64), 0.0
        import wave
        with wave.open(str(wav), "rb") as handle:
            n_frames = handle.getnframes()
            raw = handle.readframes(n_frames)
    if not raw:
        return np.zeros(0, dtype=np.float64), 0.0
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    sample_rate = 16000
    bin_size = int(sample_rate * bin_seconds)
    n_bins = len(samples) // bin_size
    if n_bins == 0:
        return np.zeros(0, dtype=np.float64), 0.0
    trimmed = samples[: n_bins * bin_size].reshape(n_bins, bin_size)
    energy = np.sqrt(np.mean(trimmed ** 2, axis=1))
    return energy, n_bins * bin_seconds


def detect_scene_changes(video_path: Path, threshold: float = 0.4) -> list[float]:
    """Return timestamps (seconds) where ffmpeg's scene detector fires."""
    result = subprocess.run(
        [FFMPEG_BINARY, "-v", "info", "-i", str(video_path),
         "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True)
    times = []
    for line in (result.stderr or "").splitlines():
        if "showinfo" in line:
            match = _SCENE_RE.search(line)
            if match:
                times.append(float(match.group(1)))
    return sorted(times)


def _speech_coverage(segments: list[dict], start: float, end: float) -> float:
    covered = 0.0
    for seg in segments:
        try:
            s, e = float(seg["start"]), float(seg["end"])
        except (KeyError, TypeError, ValueError):
            continue
        overlap = max(0.0, min(e, end) - max(s, start))
        covered += overlap
    window = max(end - start, 1e-6)
    return min(covered / window, 1.0)


def score_windows(duration: float,
                  energy: np.ndarray,
                  bin_seconds: float,
                  scenes: list[float],
                  segments: list[dict],
                  clip_duration: float,
                  step: float) -> list[dict]:
    """Score candidate windows; each dict has start/end/score."""
    if duration <= 0:
        return []
    clip_duration = min(clip_duration, duration)
    peak_energy = float(energy.max()) if energy.size else 0.0
    scenes_arr = np.array(scenes, dtype=np.float64)

    windows: list[dict] = []
    start = 0.0
    while start + clip_duration <= duration + 1e-6:
        end = start + clip_duration
        # Audio energy term: mean RMS in the window, normalized by the peak.
        if energy.size and peak_energy > 0:
            lo = int(start / bin_seconds)
            hi = min(int(end / bin_seconds), energy.size)
            energy_term = float(energy[lo:hi].mean()) / peak_energy if hi > lo else 0.0
        else:
            energy_term = 0.0
        # Scene-change density term, normalized by the densest window seen.
        scene_count = int(((scenes_arr >= start) & (scenes_arr < end)).sum())
        speech_term = _speech_coverage(segments, start, end) if segments else 0.0
        windows.append({"start": start, "end": end, "score": 0.0,
                        "_energy": energy_term, "_scenes": scene_count,
                        "_speech": speech_term})
        start += step

    if not windows:
        windows.append({"start": 0.0, "end": duration, "score": 0.0,
                        "_energy": 0.0, "_scenes": 0, "_speech": 0.0})

    peak_scenes = max(w["_scenes"] for w in windows) or 1
    for w in windows:
        w["score"] = (0.5 * w["_energy"]
                      + 0.3 * (w["_scenes"] / peak_scenes)
                      + 0.2 * w["_speech"])
        del w["_energy"], w["_scenes"], w["_speech"]
    windows.sort(key=lambda w: w["score"], reverse=True)
    return windows


def pick_top_windows(scored: list[dict], count: int) -> list[dict]:
    """Greedily take the highest-scoring windows with no time overlap."""
    picked: list[dict] = []
    for window in scored:
        if len(picked) >= count:
            break
        if all(window["end"] <= p["start"] or window["start"] >= p["end"] for p in picked):
            picked.append(window)
    picked.sort(key=lambda w: w["start"])
    return picked


def find_highlight_windows(video_path: Path,
                           segments: list[dict] | None = None,
                           count: int = 3,
                           clip_duration: float = 30.0) -> list[dict]:
    """End-to-end: detect and return the top highlight windows for a video."""
    energy, _ = audio_energy_curve(video_path)
    # Duration from the energy curve when audio exists; fall back to probing.
    duration = energy.size * _BIN_SECONDS if energy.size else 0.0
    if duration <= 0:
        from app.video.analyze import probe_video
        duration = probe_video(video_path).duration or 0.0
    if duration <= 0:
        return []
    scenes = detect_scene_changes(video_path)
    step = max(clip_duration / 4.0, 1.0)
    scored = score_windows(duration, energy, _BIN_SECONDS, scenes,
                           segments or [], clip_duration, step)
    return pick_top_windows(scored, max(count, 1))
