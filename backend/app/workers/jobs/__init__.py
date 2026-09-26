from app.workers.jobs.autocrop import run as run_autocrop
from app.workers.jobs.dubbing import run as run_dubbing
from app.workers.jobs.face_detection import run as run_face_detection
from app.workers.jobs.recap import run as run_recap
from app.workers.jobs.render import run as run_render
from app.workers.jobs.shorts import run as run_shorts
from app.workers.jobs.subtitle_burn import run as run_subtitle_burn
from app.workers.jobs.thumbnails import run as run_thumbnails
from app.workers.jobs.transcription import run as run_transcription
from app.workers.jobs.translation import run as run_translation

JOB_HANDLERS = {
    "transcription": run_transcription,
    "translation": run_translation,
    "dubbing": run_dubbing,
    "autocrop": run_autocrop,
    "face_detection": run_face_detection,
    "subtitle_burn": run_subtitle_burn,
    "render": run_render,
    "recap": run_recap,
    "shorts": run_shorts,
    "thumbnails": run_thumbnails,
}
