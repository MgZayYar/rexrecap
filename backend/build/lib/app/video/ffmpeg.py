"""FFmpeg command boundary.

Every FFmpeg subprocess call in RexCrop goes through :func:`run_ffmpeg`.
Callers work with paths and typed errors; nobody builds raw command lines
outside this module.
"""

import subprocess
from pathlib import Path

from app.core.config import FFMPEG_BINARY


class FFmpegError(RuntimeError):
    """Raised when FFmpeg is missing or a command fails."""


def run_ffmpeg(*args: str, timeout: int | None = None) -> None:
    """Run FFmpeg with the given arguments, raising :class:`FFmpegError` on failure."""
    command = [FFMPEG_BINARY, *args]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise FFmpegError("FFmpeg is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        raise FFmpegError(f"FFmpeg could not process the media: {stderr[-500:]}") from exc


def extract_audio(video_path: Path, output_path: Path) -> None:
    """Extract mono 16 kHz WAV audio for local speech-to-text inference."""
    run_ffmpeg(
        "-y",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-f", "wav",
        str(output_path),
    )
