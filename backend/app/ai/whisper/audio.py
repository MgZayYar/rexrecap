import subprocess
from pathlib import Path

from app.core.config import FFMPEG_BINARY


def extract_audio(video_path: Path, output_path: Path) -> None:
    """Extract mono 16 kHz WAV audio for local Whisper inference."""
    command = [
        FFMPEG_BINARY,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg could not extract audio: {exc.stderr[-500:]}") from exc
