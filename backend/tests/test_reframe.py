"""Unit tests for the vertical-reframe pipeline: crop math, trajectory, analysis."""

import subprocess
from pathlib import Path

import pytest

from app.video.analyze import (
    FaceSample,
    compute_crop_trajectory,
    focus_x_for_sample,
    probe_video,
    smooth_trajectory,
)
from app.video.reframe import chunk_trajectory, render_vertical, vertical_crop_size


def test_vertical_crop_size_landscape() -> None:
    assert vertical_crop_size(1920, 1080) == (608, 1080)


def test_vertical_crop_size_already_vertical_keeps_frame() -> None:
    assert vertical_crop_size(1080, 1920) == (1080, 1920)


def test_vertical_crop_size_square() -> None:
    assert vertical_crop_size(1080, 1080) == (608, 1080)


def test_smooth_trajectory_averages_neighbors() -> None:
    assert smooth_trajectory([0.0, 10.0, 20.0], window=3) == [5.0, 10.0, 15.0]


def test_smooth_trajectory_window_one_is_identity() -> None:
    assert smooth_trajectory([3.0, 1.0], window=1) == [3.0, 1.0]


def test_focus_x_prefers_face_mean() -> None:
    sample = FaceSample(t=0.0, centers_x=(100.0, 300.0))
    assert focus_x_for_sample(sample, 1920) == 200.0


def test_focus_x_without_faces_is_frame_center() -> None:
    assert focus_x_for_sample(FaceSample(t=0.0, centers_x=()), 1920) == 960.0


def test_compute_crop_trajectory_clamps_to_frame() -> None:
    samples = [FaceSample(t=float(i), centers_x=(1900.0,)) for i in range(3)]
    trajectory = compute_crop_trajectory(samples, frame_width=1920, crop_width=608)
    for _t, x in trajectory:
        assert x == 1920 - 608  # face near the right edge clamps the window


def test_compute_crop_trajectory_centers_without_faces() -> None:
    samples = [FaceSample(t=float(i), centers_x=()) for i in range(3)]
    trajectory = compute_crop_trajectory(samples, frame_width=1920, crop_width=608)
    for _t, x in trajectory:
        assert x == pytest.approx((1920 - 608) / 2)


def test_chunk_trajectory_groups_samples() -> None:
    trajectory = [(0.0, 100.0), (1.0, 110.0), (2.0, 120.0), (3.0, 130.0)]
    chunks = chunk_trajectory(trajectory, chunk_seconds=2.0)
    assert len(chunks) == 2
    assert chunks[0][2] == 105  # mean of first bucket, rounded
    assert chunks[1][0] == pytest.approx(2.0)


def _make_test_video(path: Path, size: str = "320x240", seconds: int = 3) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:duration={seconds}:rate=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True,
    )


def test_probe_video_reads_metadata(tmp_path: Path) -> None:
    video = tmp_path / "probe.mp4"
    _make_test_video(video)
    info = probe_video(video)
    assert (info.width, info.height) == (320, 240)
    assert info.duration == pytest.approx(3.0, abs=0.2)


def test_render_vertical_produces_9_16_output(tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    _make_test_video(src)
    info = probe_video(src)
    crop_size = vertical_crop_size(info.width, info.height)
    assert crop_size == (134, 240)

    samples = [FaceSample(t=float(i), centers_x=()) for i in range(6)]
    trajectory = compute_crop_trajectory(samples, info.width, crop_size[0])
    out = tmp_path / "vertical.mp4"
    render_vertical(src, out, trajectory, crop_size, info.duration)
    assert out.is_file() and out.stat().st_size > 0

    result = probe_video(out)
    assert result.width / result.height == pytest.approx(9 / 16, abs=0.02)
