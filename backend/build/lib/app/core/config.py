import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

DEFAULT_DATABASE_URL = "sqlite:///./rexcrop.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", PROJECT_DIR / "storage" / "uploads"))
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", PROJECT_DIR / "storage" / "outputs"))
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
USER_STORAGE_QUOTA_BYTES = int(os.getenv("USER_STORAGE_QUOTA_BYTES", str(10 * 1024**3)))
WORKER_POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "2.0"))

# Object storage for job-output delivery. "local" (default) streams files
# through the API; "s3" syncs finished outputs to an S3-compatible bucket
# and serves them as presigned-URL redirects. Credentials are env-only.
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "").strip() or None
S3_REGION = os.getenv("S3_REGION", "us-east-1").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip() or None
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip() or None
PRESIGNED_URL_EXPIRES_IN = int(os.getenv("PRESIGNED_URL_EXPIRES_IN", "3600"))

# Outbound email for job notifications (optional; unset SMTP_HOST disables email).
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "RexCrop <noreply@rexcrop.local>").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() not in ("0", "false", "no")
