"""Face detection API: queue an analysis job and read the JSON result."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.face_analysis import FaceAnalysis
from app.models.video import Video
from app.repositories.videos import get_owned_video
from app.schemas.face_analysis import FaceAnalysisResponse
from app.schemas.job import ProcessingJobResponse
from app.services.jobs import create_job as queue_processing_job

router = APIRouter(prefix="/faces", tags=["faces"])


@router.post("/analyze/{video_id}", response_model=ProcessingJobResponse,
             status_code=status.HTTP_201_CREATED)
async def analyze_video_faces(video_id: int, current_user: CurrentUser,
                              db: DbSession) -> ProcessingJobResponse:
    video = get_owned_video(db, video_id, current_user.id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return await queue_processing_job(db, video.id, "face_detection")


@router.get("/{video_id}", response_model=FaceAnalysisResponse)
def get_face_analysis(video_id: int, current_user: CurrentUser, db: DbSession) -> FaceAnalysis:
    analysis = db.scalar(
        select(FaceAnalysis).join(Video).where(FaceAnalysis.video_id == video_id,
                                               Video.user_id == current_user.id)
    )
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Face analysis not found")
    return analysis
