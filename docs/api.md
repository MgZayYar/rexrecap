# API

All API routes are prefixed with `/api`. Protected routes require `Authorization: Bearer <JWT>`.

## Authentication

| Method | Route | Description |
| --- | --- | --- |
| POST | `/auth/register` | Create an account with email and password. |
| POST | `/auth/login` | Return a JWT access token. |
| GET | `/auth/me` | Return the authenticated user. |

## Videos

| Method | Route | Description |
| --- | --- | --- |
| POST | `/videos/upload` | Upload an owned MP4, MOV, MKV, or AVI file as multipart field `file`. |
| GET | `/videos` | List the current user's videos. |
| GET | `/videos/{video_id}/download` | Download an owned video. |

## Processing jobs

| Method | Route | Description |
| --- | --- | --- |
| POST | `/jobs/create` | Queue a job with `video_id` and `job_type`. |
| GET | `/jobs/{job_id}` | Return an owned job. |
| GET | `/jobs/video/{video_id}` | Return jobs for an owned video, newest first. |

Allowed `job_type` values: `transcription`, `translation`, `dubbing`, `autocrop`, and `render`.

Job statuses are `queued`, `processing`, `completed`, and `failed`.

## Transcripts

| Method | Route | Description |
| --- | --- | --- |
| POST | `/transcripts/start/{video_id}` | Queue local Whisper transcription for an owned video. |
| GET | `/transcripts/{video_id}` | Return the saved transcript for an owned video. |

The transcript response includes `language`, `full_text`, and `segments`. Each segment has `start`, `end`, and `text` fields in seconds.

## Translations

| Method | Route | Description |
| --- | --- | --- |
| POST | `/translations` | Queue a translation with `video_id` and a supported ISO language code in `target_language`. A transcript is required first. |
| GET | `/translations/video/{video_id}?target_language=es` | Return the matching completed translation for an owned video. |

Translations preserve the source transcript's `start` and `end` timestamps. Reposting a failed translation retries its persisted job; reposting a completed translation returns the saved result.
