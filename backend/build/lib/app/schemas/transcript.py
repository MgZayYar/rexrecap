from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    language: str
    full_text: str
    segments: list[TranscriptSegment]
    created_at: datetime
