from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.job import ProcessingJobResponse


class CreateTranslationRequest(BaseModel):
    video_id: int = Field(gt=0)
    target_language: str = Field(min_length=2, max_length=16)


class TranslationSegment(BaseModel):
    start: float
    end: float
    text: str


class TranslationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transcript_id: int
    target_language: str
    target_language_name: str
    full_text: str | None
    segments: list[TranslationSegment] | None
    created_at: datetime
    updated_at: datetime


class TranslationJobResponse(BaseModel):
    job: ProcessingJobResponse
    translation: TranslationResponse
