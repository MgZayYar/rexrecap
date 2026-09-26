from functools import lru_cache
from pathlib import Path

from app.ai.whisper.models import TranscriptSegmentResult, TranscriptionResult
from app.core.config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL


@lru_cache(maxsize=1)
def get_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed. Install the backend dependencies first.") from exc
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)


def transcribe_audio(audio_path: Path) -> TranscriptionResult:
    model = get_model()
    segments, info = model.transcribe(str(audio_path), vad_filter=True)
    results = [
        TranscriptSegmentResult(start=round(segment.start, 3), end=round(segment.end, 3), text=segment.text.strip())
        for segment in segments
        if segment.text.strip()
    ]
    return TranscriptionResult(
        language=info.language or "unknown",
        full_text=" ".join(segment.text for segment in results),
        segments=results,
    )
