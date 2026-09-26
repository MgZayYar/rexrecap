from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size_bytes: int
    status: str
    project_id: int | None
    created_at: datetime


class VideoUpdate(BaseModel):
    """Assign, move, or unassign a video's project.

    `project_id` omitted -> no change; `null` -> unassign from its project.
    """

    project_id: int | None = None
