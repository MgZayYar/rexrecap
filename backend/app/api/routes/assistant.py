"""Recap assistant API: generate structured recap drafts from transcripts."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.recap_draft import RecapDraft
from app.models.transcript import Transcript
from app.repositories.videos import get_owned_video
from app.schemas.job import ProcessingJobResponse
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/assistant", tags=["assistant"])


class RecapDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    job_id: int
    content: dict[str, Any]
    model: str
    created_at: str | None = None


def _to_response(draft: RecapDraft) -> RecapDraftResponse:
    return RecapDraftResponse(
        id=draft.id,
        video_id=draft.video_id,
        job_id=draft.job_id,
        content=draft.content,
        model=draft.model,
        created_at=draft.created_at.isoformat() if draft.created_at else None,
    )


@router.post("/recap/{video_id}", response_model=ProcessingJobResponse,
             status_code=status.HTTP_201_CREATED)
async def generate_recap(video_id: int, current_user: CurrentUser, db: DbSession):
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    transcript = db.scalar(select(Transcript).where(Transcript.video_id == video.id))
    if transcript is None or not transcript.segments:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This video has no transcript yet — transcribe it first")
    return await queue_processing_job(db, video.id, "recap")


@router.get("/recap/video/{video_id}", response_model=list[RecapDraftResponse])
def list_drafts(video_id: int, current_user: CurrentUser, db: DbSession):
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    drafts = db.scalars(
        select(RecapDraft).where(RecapDraft.video_id == video.id)
        .order_by(RecapDraft.id.desc())
    ).all()
    return [_to_response(draft) for draft in drafts]


@router.get("/recap/{draft_id}", response_model=RecapDraftResponse)
def get_draft(draft_id: int, current_user: CurrentUser, db: DbSession):
    draft = db.scalar(
        select(RecapDraft).join(RecapDraft.video).where(
            RecapDraft.id == draft_id, RecapDraft.video.has(user_id=current_user.id))
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return _to_response(draft)
