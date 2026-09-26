# RexCrop

Monorepo for the RexCrop web application: a Next.js frontend and a FastAPI backend for AI-assisted video repurposing (transcription, translation, subtitle editing; dubbing/autocrop/render are planned).

## Structure

```text
RexCrop/
├── frontend/    # Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
├── backend/     # FastAPI, SQLAlchemy, SQLite, Alembic
└── docs/        # Architecture, API, database, and development guides
```

## Docs

- `docs/architecture.md` — module layout, layering rules, request flow
- `docs/api.md` — REST reference (`/api/v1`, legacy `/api` compatibility)
- `docs/database.md` — entities and Alembic migrations
- `docs/development.md` — setup, checks, and conventions
- `docs/roadmap.md` — what's done and what's next

## Prerequisites

- Node.js 20.9 or later
- Python 3.11 or later

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Run the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API documentation. The SQLite database is created and migrated at `backend/rexcrop.db` when the API starts (Alembic owns the schema; see `docs/database.md`).

## Environment configuration

The backend defaults to a local SQLite database and needs no environment variables for development. To override it, create `backend/.env` (see `backend/.env.example`; never commit `.env`):

```env
DATABASE_URL=<redacted>
JWT_SECRET_KEY=<a long random string>
MAX_UPLOAD_BYTES=2147483648
```

## Authentication

The API provides `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, and `GET /api/v1/auth/me` (the legacy `/api` prefix serves the same routes). Passwords are bcrypt-hashed; login issues a signed JWT.

The Next.js app keeps that token in a secure HTTP-only cookie via its own `/api/auth/*` route handlers. The dashboard validates the token against the backend on every request, while middleware redirects unauthenticated visitors before rendering protected routes.

Before deployment, set a unique `JWT_SECRET_KEY` in `backend/.env`. The included `.env.example` files show the supported environment variables.

## Video uploads

Authenticated users can upload MP4, MOV, MKV, or AVI files from `/upload`. Files are stored locally in `backend/storage/uploads/`; video metadata and ownership are recorded in SQLite. Uploads are streamed with an enforced size limit (`MAX_UPLOAD_BYTES`, default 2 GiB; 413 when exceeded). The dashboard lists each user's uploads and provides a protected download action. AI/video processing is intentionally not included.

## Projects

Authenticated users can organize their work into projects (`POST /api/v1/projects`, plus list/get/patch/delete). Projects are strictly user-owned: every project route is ownership-scoped. Videos are not yet linked to projects; that association is a planned follow-up migration.

## Processing jobs

`POST /api/v1/jobs/create` queues a processing job for an owned video. Supported job types are `transcription`, `translation`, `dubbing`, `autocrop`, and `render`. The API process starts an in-memory worker at startup; it polls persisted queued jobs and saves the final status. `dubbing`, `autocrop`, and `render` are placeholders that simulate progress without producing output. This is intentionally a development framework—the queue is not shared across processes.

Each uploaded video has workflow controls on the dashboard. The transcript page includes authenticated in-browser playback; selecting a timestamp seeks the video and starts playback.

## Speech-to-text

`POST /api/v1/transcripts/start/{video_id}` queues local Whisper transcription for an owned video; `GET /api/v1/transcripts/{video_id}` returns the saved transcript. Transcription extracts 16 kHz WAV audio with FFmpeg, automatically detects language, and saves timestamped segments in SQLite. Install FFmpeg and ensure `ffmpeg` is on your PATH (or set `FFMPEG_BINARY`). `faster-whisper` downloads the configured local model (`base` by default) the first time it runs; choose a model and CPU/GPU settings with the `WHISPER_*` variables in `backend/.env`.

## Translation

After a transcript is available, choose one of 60+ target languages in the transcript view. RexCrop preserves each source timestamp and uses the OpenAI Responses API to translate segment text in batches. Set `OPENAI_API_KEY` in `backend/.env`; `TRANSLATION_MODEL` defaults to `gpt-4.1-mini` and can be changed without code changes. Failed translations can be retried from the same language selector.

## Subtitle editing

Open **Edit subtitles** from a video on the dashboard to refine transcript cues in a browser-based editor. It includes timeline handle dragging, text and time editing, merge/split tools, search, undo/redo shortcuts, style controls, and SRT or ASS exports. Edits remain in the browser until exported.

## Tests

Backend: `cd backend && .venv/Scripts/python -m pytest -q` (representative suite: auth, projects, videos incl. upload limits, jobs).
Frontend: `cd frontend && npm test` (Vitest), plus `npm run typecheck`, `npm run lint`, and `npm run build`.
