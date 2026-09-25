# RexCrop

Starter monorepo for the RexCrop web application. It contains a Next.js frontend and a FastAPI backend, ready for development. Business logic has intentionally not been implemented.

## Structure

```text
RexCrop/
├── frontend/    # Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
└── backend/     # FastAPI, SQLAlchemy, SQLite
```

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

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API documentation. The SQLite database is created at `backend/rexcrop.db` when the API starts.

## Environment configuration

The backend defaults to a local SQLite database and needs no environment variables for development. To override it, create `backend/.env` with:

```env
DATABASE_URL=sqlite:///./rexcrop.db
```

## Authentication

The API provides `POST /api/auth/register`, `POST /api/auth/login`, and `GET /api/auth/me`. Passwords are bcrypt-hashed; login issues a signed JWT.

The Next.js app keeps that token in a secure HTTP-only cookie via its own `/api/auth/*` route handlers. The dashboard validates the token against the backend on every request, while middleware redirects unauthenticated visitors before rendering protected routes.

Before deployment, set a unique `JWT_SECRET_KEY` in `backend/.env`. The included `.env.example` files show the supported environment variables.

## Video uploads

Authenticated users can upload MP4, MOV, MKV, or AVI files from `/upload`. Files are stored locally in `backend/storage/uploads/`; video metadata and ownership are recorded in SQLite. The dashboard lists each user's uploads and provides a protected download action. AI/video processing is intentionally not included.

## Processing jobs

`POST /api/jobs/create` queues a placeholder processing job for an owned video. Supported job types are `transcription`, `translation`, `dubbing`, `autocrop`, and `render`. The API process starts an in-memory worker at startup; it polls persisted queued jobs, simulates progress, and saves the final status. This is intentionally a development framework—no AI work is performed and the queue is not shared across processes.

Each uploaded video has workflow controls on the dashboard. The transcript page includes authenticated in-browser playback; selecting a timestamp seeks the video and starts playback.

## Speech-to-text

`POST /api/transcripts/start/{video_id}` queues local Whisper transcription for an owned video; `GET /api/transcripts/{video_id}` returns the saved transcript. Transcription extracts 16 kHz WAV audio with FFmpeg, automatically detects language, and saves timestamped segments in SQLite. Install FFmpeg and ensure `ffmpeg` is on your PATH (or set `FFMPEG_BINARY`). `faster-whisper` downloads the configured local model (`base` by default) the first time it runs; choose a model and CPU/GPU settings with the `WHISPER_*` variables in `backend/.env`.

## Translation

After a transcript is available, choose one of 60+ target languages in the transcript view. RexCrop preserves each source timestamp and uses the OpenAI Responses API to translate segment text in batches. Set `OPENAI_API_KEY` in `backend/.env`; `TRANSLATION_MODEL` defaults to `gpt-4.1-mini` and can be changed without code changes. Failed translations can be retried from the same language selector.

## Subtitle editing

Open **Edit subtitles** from a video on the dashboard to refine transcript cues in a browser-based editor. It includes timeline handle dragging, text and time editing, merge/split tools, search, undo/redo shortcuts, style controls, and SRT or ASS exports. Edits remain in the browser until exported.
