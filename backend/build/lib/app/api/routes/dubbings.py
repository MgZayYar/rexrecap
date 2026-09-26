"""Dubbing REST API: voice catalog, voice preview, and dub job creation."""

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.dubbing.providers import PROVIDERS, Voice, get_provider
from app.ai.dubbing.voices import list_voices as provider_voices
from app.ai.dubbing.voices import resolve_voice
from app.api.deps import CurrentUser, DbSession
from app.models.transcript import Transcript
from app.models.translation import Translation
from app.models.video import Video
from app.repositories.videos import get_owned_video
from app.schemas.job import ProcessingJobResponse
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/dubbings", tags=["dubbing"])


class VoiceResponse(BaseModel):
    id: str
    name: str
    language: str
    gender: str
    provider: str


class PreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    voice: str = Field(min_length=1)
    provider: str = "edge"


class StartDubbingRequest(BaseModel):
    provider: str = "edge"
    voice: str | None = None
    target_language: str | None = Field(default=None, min_length=2, max_length=16)


def _voice_response(voice: Voice) -> VoiceResponse:
    return VoiceResponse(id=voice.id, name=voice.name, language=voice.language,
                         gender=voice.gender, provider=voice.provider)


@router.get("/voices", response_model=list[VoiceResponse])
async def list_dubbing_voices(provider: str = "edge", language: str | None = None):
    try:
        voices = await provider_voices(provider, language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return [_voice_response(v) for v in voices]


@router.get("/providers", response_model=list[str])
def list_dubbing_providers() -> list[str]:
    return sorted(PROVIDERS)


@router.post("/preview")
async def preview_voice(payload: PreviewRequest) -> Response:
    """Render a short sample so the user can hear a voice before dubbing."""
    try:
        provider = get_provider(payload.provider)
        voice = await resolve_voice(payload.provider, language="", voice_id=payload.voice)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="rexcrop-preview-") as tmp:
        path = Path(tmp) / "preview.mp3"
        try:
            await provider.synthesize(payload.text, voice.id, path)
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        audio = path.read_bytes()
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/start/{video_id}", response_model=ProcessingJobResponse,
             status_code=status.HTTP_201_CREATED)
async def start_dubbing(video_id: int, payload: StartDubbingRequest,
                        current_user: CurrentUser, db: DbSession):
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    transcript = db.scalar(
        select(Transcript).where(Transcript.video_id == video.id)
    )
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Generate a transcript before starting dubbing")

    target_language = (payload.target_language or "").lower() or None
    if target_language:
        translation = db.scalar(
            select(Translation)
            .join(Transcript, Translation.transcript_id == Transcript.id)
            .where(Transcript.video_id == video.id,
                   Translation.target_language == target_language)
        )
        if translation is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"No {target_language} translation exists for this video")

    try:
        get_provider(payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    params = {"provider": payload.provider, "voice": payload.voice,
              "target_language": target_language}
    return await queue_processing_job(db, video.id, "dubbing", params=params)
