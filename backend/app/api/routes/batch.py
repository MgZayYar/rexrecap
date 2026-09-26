"""Batch runs API: queue one job type across many videos."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models.batch_run import BatchRun, BatchRunItem
from app.services.batch import BATCHABLE_JOB_TYPES, MAX_BATCH_VIDEOS, batch_summary, create_batch_run

router = APIRouter(prefix="/batch", tags=["batch"])


class CreateBatchRequest(BaseModel):
    job_type: str = Field(min_length=1, max_length=50)
    video_ids: list[int] = Field(min_length=1, max_length=MAX_BATCH_VIDEOS)
    params: dict = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=255)


class BatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    total: int
    queued: int
    processing: int
    completed: int
    failed: int
    cancelled: int


class BatchRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    job_type: str
    created_at: str | None = None
    summary: BatchSummary


class BatchRunItemResponse(BaseModel):
    video_id: int
    filename: str
    job_id: int
    job_status: str
    job_progress: int


class BatchRunDetailResponse(BatchRunResponse):
    items: list[BatchRunItemResponse]


def _load_batch(db: DbSession, batch_id: int, user_id: int) -> BatchRun:
    batch = db.scalar(
        select(BatchRun)
        .options(selectinload(BatchRun.items).selectinload(BatchRunItem.job),
                 selectinload(BatchRun.items).selectinload(BatchRunItem.video))
        .where(BatchRun.id == batch_id, BatchRun.user_id == user_id)
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Batch run not found")
    return batch


def _to_response(batch: BatchRun) -> BatchRunResponse:
    created = batch.created_at.isoformat() if batch.created_at else None
    return BatchRunResponse(
        id=batch.id,
        label=batch.label,
        job_type=batch.job_type,
        created_at=created,
        summary=BatchSummary(**batch_summary(batch)),
    )


@router.post("/runs", response_model=BatchRunResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(payload: CreateBatchRequest, current_user: CurrentUser, db: DbSession):
    if payload.job_type not in BATCHABLE_JOB_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Job type '{payload.job_type}' cannot be batched")
    try:
        batch = await create_batch_run(db, current_user.id, payload.job_type,
                                       payload.video_ids, payload.params, payload.label)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=str(exc)) from exc
    return _to_response(_load_batch(db, batch.id, current_user.id))


@router.get("/runs", response_model=list[BatchRunResponse])
def list_batches(current_user: CurrentUser, db: DbSession):
    batches = db.scalars(
        select(BatchRun)
        .options(selectinload(BatchRun.items).selectinload(BatchRunItem.job))
        .where(BatchRun.user_id == current_user.id)
        .order_by(BatchRun.id.desc())
        .limit(100)
    ).all()
    return [_to_response(batch) for batch in batches]


@router.get("/runs/{batch_id}", response_model=BatchRunDetailResponse)
def get_batch(batch_id: int, current_user: CurrentUser, db: DbSession):
    batch = _load_batch(db, batch_id, current_user.id)
    response = _to_response(batch)
    items = [
        BatchRunItemResponse(
            video_id=item.video_id,
            filename=item.video.filename if item.video else f"video {item.video_id}",
            job_id=item.job_id,
            job_status=item.job.status if item.job else "queued",
            job_progress=item.job.progress if item.job else 0,
        )
        for item in sorted(batch.items, key=lambda i: i.id)
    ]
    return BatchRunDetailResponse(**response.model_dump(), items=items)
