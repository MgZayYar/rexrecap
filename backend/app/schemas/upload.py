from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadSessionCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    total_bytes: int = Field(gt=0)
    project_id: int | None = None


class UploadSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    total_bytes: int
    received_bytes: int
    project_id: int | None
    status: str
    created_at: datetime


class QuotaResponse(BaseModel):
    quota_bytes: int
    used_bytes: int
    available_bytes: int
