# Database

Development uses SQLite. The default database URL is `sqlite:///./rexcrop.db`, so when FastAPI is run from `backend/`, the file is created at `backend/rexcrop.db`.

## Migrations (Alembic)

Alembic owns the schema. At startup the app runs `alembic upgrade head` (see `backend/app/db/migrations.py`), which converges fresh and existing databases to the current revision without destroying data.

- Migration files live in `backend/alembic/versions/` and are numbered sequentially (`0001_...`, `0002_...`).
- `0001_baseline_schema.py` creates all tables. It is idempotent: every table and index is created only when missing, so it is safe on databases that were created by the old `Base.metadata.create_all()` bootstrap.
- ⚠️ **Do not run `alembic downgrade` on the baseline migration against a database that already had tables.** Downgrading `0001` drops the tables it created; on an adopted (pre-Alembic) database that means destroying real user data. The baseline migration is meant to be upgraded through, never downgraded from.
- `0002_job_output_path.py` adds the nullable `output_path` column to `processing_jobs` for jobs that produce downloadable files.
- Never edit a migration that has already run anywhere; add a new one instead.

### Working with migrations

```powershell
cd backend
# Create a new migration after changing models (review the generated file!)
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
# Apply migrations to the configured database
.venv\Scripts\alembic upgrade head
# Inspect history
.venv\Scripts\alembic history
```

`alembic/env.py` reads `DATABASE_URL` from `app.core.config` (the same source the app uses) and resolves relative SQLite paths against `backend/`, so the CLI behaves the same regardless of the working directory.

## Entities

| Entity | Purpose | Important relations |
| --- | --- | --- |
| `User` | Authenticated account | Owns videos and projects. |
| `Project` | User-owned container grouping a user's work | Belongs to a user. |
| `Video` | Uploaded-file metadata | Belongs to a user; has processing jobs and one transcript. |
| `ProcessingJob` | State for asynchronous work | Belongs to a video. |
| `Transcript` | Whisper output | One record per video. |
| `Translation` | OpenAI translation output | Belongs to one transcript and one processing job; unique per target language. |

## ProcessingJob

`ProcessingJob` stores the requested `job_type`, lifecycle `status`, integer `progress`, optional `error_message`, and lifecycle timestamps. The worker is the only component that transitions work from `queued` to a terminal state.

## Transcript

`Transcript.segments` is a JSON list. Each element is stored as:

```json
{ "start": 12.34, "end": 16.82, "text": "Transcript segment text." }
```

## Translation

`Translation.segments` uses the same timestamped JSON shape as `Transcript.segments`. The worker writes translated text only, copying the source `start` and `end` values unchanged.

## Project

`Project` has a user-scoped `name` (trimmed, never blank), an optional `description`, and a `status` of `active` or `archived`. Deleting a user cascades to their projects. Videos are not yet linked to projects; that association is a planned follow-up migration (see `docs/roadmap.md`).
