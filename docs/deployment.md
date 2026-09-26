# Deployment

RexCrop ships as three containers: the FastAPI **api**, the standalone
**worker** (same image, different command), and the Next.js **web** frontend.
Alembic migrations run automatically when the API starts, so a fresh database
converges to the current schema with no manual step.

## Quick start

```bash
cp .env.example .env
# edit .env: set JWT_SECRET_KEY at minimum
docker compose up --build
```

Open http://localhost:3000 and register an account.

With S3-compatible object storage for job-output delivery:

```bash
docker compose --profile storage up --build
```

then set `STORAGE_BACKEND=s3` and the `S3_*` variables in `.env` (see
`.env.example`; the `storage-init` service creates the `rexcrop-outputs`
bucket in MinIO automatically).

## How the pieces fit

- **api** serves the REST API on port 8000 and runs Alembic migrations on
  startup. Health probe: `GET /health` (200 when the database and storage are
  reachable, 503 otherwise) — wired as the container `HEALTHCHECK`.
- **worker** runs `python -m app.workers.runner`, claiming jobs from the
  database. Run more replicas for parallel jobs; claiming is atomic.
- **web** is the Next.js standalone server on port 3000. It talks to the API
  server-side via `API_URL` (default `http://api:8000/api/v1` in compose), so
  browsers never need direct API access and no CORS configuration is required.
- Volumes: `rexcrop-data` holds the SQLite database, uploads, and outputs.
  Back it up as files — stop the stack or snapshot the volume; SQLite WAL
  mode is enabled so the api and worker can write concurrently.

## Production checklist

- `JWT_SECRET_KEY` must be a long random secret; the API logs a warning on
  the default development key.
- Put the stack behind a reverse proxy (Caddy/Traefik/Nginx) for TLS and
  forward `https://your-host` to `web:3000`. The auth cookie is `Secure` in
  production automatically.
- Resource sizing: transcription (faster-whisper, default `base` model) and
  FFmpeg rendering are CPU-heavy; give the worker 2+ vCPUs and a few GB of
  RAM. First transcription downloads the Whisper model (~150 MB for `base`)
  into the container — it persists in the image layer cache, not the volume.
- Uploads: the default 2 GB `MAX_UPLOAD_BYTES` and 10 GB per-user quota can
  be raised via env, but keep the reverse proxy's client-body limit in sync.
- Email alerts need the `SMTP_*` variables; webhooks need no extra config.
- For AWS S3 instead of MinIO, omit `S3_ENDPOINT_URL` and set real
  credentials; the bucket must exist.

## Without Docker

The compose file is the reference, but nothing requires it:

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
cd backend && python -m app.workers.runner   # separate process
cd frontend && npm run build && npm start    # API_URL=http://127.0.0.1:8000/api/v1
```

Migrations still run automatically via the API lifespan.
