from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobType = Literal["transcription", "translation", "dubbing", "autocrop", "render"]
JobStatus = Literal["queued", "processing", "completed", "failed"]


class CreateJobRequest(BaseModel):
    video_id: int = Field(gt=0)
    job_type: JobType


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    job_type: JobType
    status: JobStatus
    progress: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
