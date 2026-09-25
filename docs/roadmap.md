# Roadmap

## Current foundation

- Cookie-based JWT authentication
- Per-user video uploads and secure downloads
- SQLite metadata storage
- In-process processing-job queue and dashboard status polling
- Local Whisper transcription with FFmpeg audio extraction
- Transcript search and copy interface

## Next

- Add file-size limits, quotas, and resumable uploads.
- Add Alembic migrations and automated backend/frontend tests.
- Move workers to a separate process with Redis or another durable queue.

## Later

- Implement translation, dubbing, autocrop, and render jobs.
- Add object storage and background delivery for large media files.
- Add job cancellation, retry, observability, and notifications.
- Add organization/workspace roles and production deployment configuration.
