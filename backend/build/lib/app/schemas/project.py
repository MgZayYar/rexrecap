from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectStatus = Literal["active", "archived"]


def _require_non_blank_name(value: str | None) -> str | None:
    """Strip whitespace and reject blank names (a name of only spaces is empty)."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("name must not be blank")
    return stripped


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        return _require_non_blank_name(value)  # type: ignore[return-value]


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        return _require_non_blank_name(value)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
