from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.batch import router as batch_router
from app.api.routes.dubbings import router as dubbings_router
from app.api.routes.shorts import router as shorts_router
from app.api.routes.faces import router as faces_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.projects import router as projects_router
from app.api.routes.subtitles import router as subtitles_router
from app.api.routes.thumbnails import router as thumbnails_router
from app.api.routes.transcripts import router as transcripts_router
from app.api.routes.translations import router as translations_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.videos import router as videos_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(batch_router)
api_router.include_router(dubbings_router)
api_router.include_router(shorts_router)
api_router.include_router(faces_router)
api_router.include_router(jobs_router)
api_router.include_router(notifications_router)
api_router.include_router(projects_router)
api_router.include_router(subtitles_router)
api_router.include_router(thumbnails_router)
api_router.include_router(transcripts_router)
api_router.include_router(translations_router)
api_router.include_router(uploads_router)
api_router.include_router(videos_router)
