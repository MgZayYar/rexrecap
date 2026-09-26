# RexCrop backend: FastAPI API + standalone worker (same image, different command).
FROM python:3.12-slim

# ffmpeg/ffprobe do the actual video work; ca-certificates for TLS
# (S3-compatible storage, webhooks, SMTP, OpenAI/Edge TTS).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/rexcrop

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
RUN pip install --no-cache-dir .

# Sensible container defaults; override in compose / your orchestrator.
ENV PYTHONUNBUFFERED=1 \
    DATABASE_URL="sqlite:////data/rexcrop.db" \
    UPLOADS_DIR=/data/uploads \
    OUTPUTS_DIR=/data/outputs

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"

# API by default; the worker service overrides the command with:
#   python -m app.workers.runner
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
