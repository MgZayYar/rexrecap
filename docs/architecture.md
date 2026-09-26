# Architecture

RexCrop is a two-application workspace:

```text
frontend/  Next.js 15 application (backend-for-frontend + browser UI)
backend/   FastAPI application and local worker
```

## Backend

The FastAPI application owns authentication, SQLite persistence, uploaded files, job state, and local AI integrations. Modules are organized by responsibility:

```text
backend/
├── alembic/            # Database migrations (Alembic)
│   ├── env.py          # Migration environment, reads DATABASE_URL from app config
│   └── versions/       # Sequential migrations, e.g. 0001_baseline_schema.py
├── alembic.ini
└── app/
    ├── api/
    │   ├── deps.py     # Shared dependencies (current user, DB session)
    │   ├── router.py   # Aggregates route modules
    │   └── routes/     # One module per resource: auth, videos, jobs,
    │                   # transcripts, translations, projects
    ├── ai/             # Local AI adapters, including Whisper
    ├── core/           # Configuration (env-driven, no hard-coded secrets)
    ├── db/
    │   ├── base.py     # SQLAlchemy declarative base
    │   ├── session.py  # Engine and session factory
    │   └── migrations.py  # Runs `alembic upgrade head` at startup
    ├── models/         # Database entities
    ├── repositories/   # Ownership-scoped data access (videos, projects)
    ├── schemas/        # Pydantic request/response contracts
    ├── services/
    │   ├── jobs.py     # Job creation + enqueue (transaction-safe variants)
    │   └── ...         # Domain services (languages, translation, ...)
    ├── video/          # Storage and media-processing boundary (ffmpeg)
    └── workers/        # In-process queue and job handlers
```

### Layering rules

- **Routes** handle HTTP only: parse input, call repositories/services, return schemas. They never contain SQL or business logic.
- **Repositories** encapsulate ownership-scoped queries (`get_owned_video`, `list_user_projects`). Every cross-user read goes through them.
- **Services** own multi-step application logic such as job creation. `services/jobs.py` offers `create_job()` for the simple case and `create_job_record()` + `enqueue_job()` when dependent rows (e.g. a `Translation`) must be committed atomically before the worker can see the job.
- **`app/video/`** is the single boundary for media processing. FFmpeg invocation lives in `app/video/ffmpeg.py`; nothing else shells out to media tools.
- **Errors** are centralized: predictable JSON `{ detail }` responses via exception handlers in `app/main.py`.

### API versioning

Routes are mounted twice: canonical `/api/v1/...` and legacy `/api/...` for backward compatibility. New clients use `/api/v1`. See `docs/api.md`.

### Database

Alembic owns the schema. At startup the app runs `alembic upgrade head`, which converges fresh and existing databases to the current revision without destroying data. See `docs/database.md`.

### Background jobs

At API startup, a worker starts in the same process. It polls persisted queued jobs and handles them one at a time. This is suitable for local development; production should move job execution to a separate worker process backed by durable shared infrastructure.

## Frontend

```text
frontend/src/
├── app/
│   ├── api/…/route.ts   # Backend-for-frontend route handlers (server only)
│   └── …/page.tsx       # Server components for pages
├── components/          # Client components (use lib/api-client)
└── lib/
    ├── api-client.ts    # Typed fetch wrapper for browser components
    ├── server-backend.ts# Auth-cookie + backend proxy helpers (server only)
    ├── backend.ts       # Backend base URL + error parsing
    └── …                # Domain helpers (video, transcript, subtitle, job)
```

- **Route handlers** (`app/api/**/route.ts`) are thin: they read the auth cookie via `server-backend.ts`, forward to FastAPI, and proxy the response. They never embed business logic.
- **Browser components** call the Next.js `/api` routes through `lib/api-client.ts` (`apiGet`/`apiPost`), which normalizes errors into `ApiError` with a user-facing `detail`.
- JWTs live in HTTP-only, same-site cookies. Browser code never receives the token directly.

## Request flow

1. The user signs in through a Next.js route handler, which exchanges credentials for a JWT and stores it in an HTTP-only cookie.
2. Browser components call `/api/...` (Next.js) via `api-client.ts`.
3. Route handlers attach the JWT and proxy to FastAPI (`/api/v1/...`).
4. FastAPI validates ownership through repositories, persists via SQLAlchemy, and enqueues jobs; the worker processes them asynchronously.
5. The UI polls job status and renders transcripts, translations, and the subtitle editor.
