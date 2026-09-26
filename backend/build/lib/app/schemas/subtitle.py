from typing import Literal

from pydantic import BaseModel


class BurnSubtitlesRequest(BaseModel):
    source: Literal["transcript", "translation"] = "transcript"
    format: Literal["srt", "ass"] = "ass"
    language: str | None = None
