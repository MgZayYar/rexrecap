# Database

Development uses SQLite. The default database URL is `sqlite:///./rexcrop.db`, so when FastAPI is run from `backend/`, the file is created at `backend/rexcrop.db`.

## Entities

| Entity | Purpose | Important relations |
| --- | --- | --- |
| `User` | Authenticated account | Owns videos. |
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

`Base.metadata.create_all()` creates missing tables at FastAPI startup. For production schema evolution, introduce Alembic migrations before deploying changes to existing data.

## Translation

`Translation.segments` uses the same timestamped JSON shape as `Transcript.segments`. The worker writes translated text only, copying the source `start` and `end` values unchanged.
