from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegmentResult:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    language: str
    full_text: str
    segments: list[TranscriptSegmentResult]
