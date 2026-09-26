from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

JobType = Literal["transcription", "translation", "dubbing", "autocrop", "face_detection", "subtitle_burn", "render"]
JobStatus = Literal["queued", "processing", "completed", "failed"]


class CreateJobRequest(BaseModel):
    video_id: int = Field(gt=0)
    job_type: JobType
    params: dict | None = None


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
    params: dict | None = None
    output_path: str | None = Field(default=None, exclude=True, repr=False)

    @computed_field
    @property
    def has_output(self) -> bool:
        """True when the job produced a downloadable file."""
        return bool(self.output_path)
