import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

DEFAULT_DATABASE_URL = "sqlite:///./rexcrop.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
UPLOADS_DIR = PROJECT_DIR / "storage" / "uploads"
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "gpt-4.1-mini")
DEFAULT_JWT_SECRET_KEY = "change-this-development-secret-before-production"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET_KEY)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024**3)))
