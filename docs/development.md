# Development

## Prerequisites

- Node.js 20.9 or later
- Python 3.11 or later
- FFmpeg on `PATH` (or set `FFMPEG_BINARY`) for transcription

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copy `backend/.env.example` to `backend/.env` to override defaults (never commit `.env`):

```env
DATABASE_URL=<redacted>
JWT_SECRET_KEY=<a long random string>
MAX_UPLOAD_BYTES=2147483648
```

Run the API:

```powershell
uvicorn app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API documentation. The SQLite database is created/migrated at `backend/rexcrop.db` on startup.

### Backend checks

```powershell
cd backend
.venv\Scripts\python -m pytest -q        # representative test suite
.venv\Scripts\python -m compileall -q app tests
```

Database migrations: see `docs/database.md`.

## Frontend

```powershell
cd frontend
npm install
npm run dev        # http://localhost:3000
```

`frontend/.env.example` documents `API_URL` (defaults to `http://127.0.0.1:8000/api/v1`).

### Frontend checks

```powershell
cd frontend
npm run typecheck  # tsc --noEmit
npm run lint
npm test           # vitest run
npm run build      # production build
```

## Conventions

- Backend routes stay thin: HTTP parsing in `app/api/routes/`, ownership-scoped queries in `app/repositories/`, multi-step logic in `app/services/`.
- Media processing goes through `app/video/`; nothing else shells out to FFmpeg.
- Schema changes always get an Alembic migration — never edit an applied migration.
- Frontend browser components use `lib/api-client.ts`; server route handlers use `lib/server-backend.ts`. Browser code never touches the JWT directly.
- Keep tests representative, not exhaustive: a few tests per area that guard the contracts that matter.
