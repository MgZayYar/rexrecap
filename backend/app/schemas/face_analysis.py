from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FaceAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    result: dict[str, Any]
    created_at: datetime
