# API

All routes are served under the canonical `/api/v1` prefix. The unversioned `/api` prefix serves the same routes for backward compatibility; new clients should use `/api/v1`.

Protected routes require `Authorization: Bearer <JWT>`. The Next.js frontend keeps the token in an HTTP-only cookie and attaches it in its backend-for-frontend handlers, so browser code never handles the token directly.

Errors are JSON: `{ "detail": "<message>" }`.

Every resource is user-owned: a request for another user's video, job, project, or setting returns 404 (or 400 where noted), never their data.

Interactive OpenAPI docs are served by the backend itself at `/docs` (Swagger UI) and `/openapi.json`.

## Health

Unauthenticated. Used by load balancers and the container `HEALTHCHECK`.

| Method | Route | Description |
| --- | --- | --- |
| GET | `/health` | Returns 200 `{ "status": "ok", ... }` when the database and storage are reachable, 503 when degraded. |

## Authentication

| Method | Route | Description |
| --- | --- | --- |
| POST | `/auth/register` | Create an account with email and password. Returns 201. |
| POST | `/auth/login` | Return a JWT access token. |
| GET | `/auth/me` | Return the authenticated user. |

## Projects

Projects are user-owned containers that group a user's work. Every project route is ownership-scoped: users can only see and mutate their own projects.

| Method | Route | Description |
| --- | --- | --- |
| POST | `/projects` | Create a project. Body: `{ "name", "description?" }`. Names are trimmed and must not be blank. Returns 201. |
| GET | `/projects` | List the current user's projects. |
| GET | `/projects/{project_id}` | Get one owned project. 404 if missing or owned by someone else. |
| PATCH | `/projects/{project_id}` | Update `name`, `description`, or `status` (`active` \| `archived`). |
| DELETE | `/projects/{project_id}` | Delete an owned project. Its videos are kept and become unassigned. Returns 204. |
| GET | `/projects/{project_id}/videos` | List the current user's videos assigned to the project. |

## Videos

| Method | Route | Description |
| --- | --- | --- |
| POST | `/videos/upload` | Upload an owned MP4, MOV, MKV, or AVI file as multipart field `file`. Optional `project_id` form field assigns the video to an owned project. Enforces the `MAX_UPLOAD_BYTES` limit and the per-user storage quota (413 when exceeded). Returns 201. |
| GET | `/videos/quota` | The current user's storage usage: `{ quota_bytes, used_bytes, available_bytes }`. |
| POST | `/videos/uploads` | Start a resumable upload session. Body: `{ filename, content_type, total_bytes, project_id? }`. Validates the quota up front. Returns 201 with the session (offset 0). |
| GET | `/videos/uploads/{upload_id}` | Read the session, including the server-confirmed `received_bytes` offset for resuming. |
| PATCH | `/videos/uploads/{upload_id}` | Append one chunk (raw body) with the `Upload-Offset` header matching the server offset. 409 on offset mismatch (re-read the session and continue). Returns the updated session. |
| POST | `/videos/uploads/{upload_id}/complete` | Finalize a fully-received session into a video. Returns 201. |
| DELETE | `/videos/uploads/{upload_id}` | Abort a session and delete the partial file. Returns 204. |
| GET | `/videos` | List the current user's videos. |
| PATCH | `/videos/{video_id}` | Assign, move, or unassign a video's project. Body: `{ "project_id": number \| null }`; omitting the field leaves the assignment unchanged. 404 for a foreign project. |
| GET | `/videos/{video_id}/download` | Download an owned video. |
| GET | `/videos/{video_id}/playback` | Stream an owned video (supports `Range` requests). |

## Processing jobs

Jobs run in the standalone worker (`python -m app.workers.runner`), which claims the oldest queued row from the database. Statuses: `queued` → `processing` → `completed` | `failed` | `cancelled`.

Job types: `transcription`, `translation`, `dubbing`, `autocrop`, `face_detection`, `subtitle_burn`, `render`, `shorts`, `thumbnails`, `recap`. The `render` worker assembles the final delivery MP4 (`<uuid>_render.mp4`); the optional `params` object carries per-job options — the autocrop worker reads `params.aspect_ratio` (`"9:16"` default, also `"1:1"` and `"4:5"`), and the render worker reads `params.aspect_ratio` (smart-crop stage), `params.burn_subtitles` (`"ass"`/`"srt"`), `params.subtitle_source` (`"transcript"`/`"translation"`), `params.language`, and `params.use_dubbed_audio` (replaces the audio track with the video's latest completed dubbing output). Job responses include `has_output: true` when a download is available.

| Method | Route | Description |
| --- | --- | --- |
| POST | `/jobs/create` | Queue a processing job for an owned video. Body: `{ video_id, job_type, params? }`. Returns 201. |
| GET | `/jobs` | List the current user's jobs, newest first. Optional `status` and `video_id` query filters, plus `limit` (default 100, max 500). |
| GET | `/jobs/video/{video_id}` | List jobs for one owned video. |
| GET | `/jobs/{job_id}` | One owned job. |
| POST | `/jobs/{job_id}/cancel` | Cancel a job. Queued jobs stop immediately; a running job is aborted cooperatively at its next progress checkpoint. 409 for terminal jobs. |
| POST | `/jobs/{job_id}/retry` | Requeue a failed or cancelled job. 409 for anything else. |
| GET | `/jobs/{job_id}/output` | Download the job's output file. When the output was synced to object storage (`STORAGE_BACKEND=s3`), responds 302 to a presigned URL instead of streaming. |
| GET | `/jobs/workers` | Worker heartbeats: `worker_id`, `started_at`, `last_seen`, `current_job_id`, and computed `is_live`. |

## Notifications

Email (SMTP) and webhook alerts fired by the worker after each terminal job state. Notification failures are logged and never fail the job.

| Method | Route | Description |
| --- | --- | --- |
| POST | `/notifications/settings` | Create a setting: `{ "channel": "email" \| "webhook", "target", "events": ["completed", "failed", "cancelled"], "enabled" }`. Returns 201. |
| GET | `/notifications/settings` | List my notification settings. |
| PATCH | `/notifications/settings/{setting_id}` | Update target, events, or enabled. |
| DELETE | `/notifications/settings/{setting_id}` | Delete a setting. Returns 204. |
| POST | `/notifications/settings/{setting_id}/test` | Send a test ping through the setting. 502 with details when delivery fails. |

Webhook deliveries are `POST` requests with an `X-RexCrop-Event` header naming the event (`job_completed`, `job_failed`, `job_cancelled`).

## Batch

Queue one job type across many videos at once (up to 50). Each video gets its own processing job; the batch groups them for progress tracking. Summaries are derived from the live job statuses, so they stay accurate without any background updater.

| Method | Route | Description |
| --- | --- | --- |
| POST | `/batch/runs` | Create a batch. Body: `{ "job_type", "video_ids": [...], "params"?, "label"? }`. `job_type` must be batchable (`transcription`, `translation`, `dubbing`, `autocrop`, `face_detection`, `subtitle_burn`, `render`, `shorts`, `thumbnails`, `recap`). 400 for foreign or unknown video ids, or an unbatchable type. Returns 201 with a progress summary. |
| GET | `/batch/runs` | List my batch runs, newest first, each with its summary. |
| GET | `/batch/runs/{batch_id}` | One batch with per-video items: `filename`, `job_id`, `job_status`, `job_progress`. |

## Thumbnails

| Method | Route | Description |
| --- | --- | --- |
| POST | `/thumbnails/generate/{video_id}` | Queue a `thumbnails` job. Body: `{ "count" }` (1–16, default 8). The worker extracts frames spread across the video and scores them by sharpness plus face prominence. Returns 201. |
| GET | `/thumbnails/video/{video_id}` | List candidates for an owned video, best score first, each with a `selected` flag. |
| GET | `/thumbnails/{thumbnail_id}/image` | Serve one candidate as JPEG. |
| POST | `/thumbnails/{thumbnail_id}/select` | Set the candidate as the video's thumbnail (`videos.thumbnail_path`). |

## Recap assistant

Turns a finished transcript into a structured recap draft (title ideas, opening hook, timestamped story beats, key quotes) using the OpenAI Responses API. Requires `OPENAI_API_KEY` on the server; the model is `RECAP_MODEL` (default `gpt-4.1-mini`).

| Method | Route | Description |
| --- | --- | --- |
| POST | `/assistant/recap/{video_id}` | Queue a `recap` job. 409 when the video has no transcript yet. Returns 201. |
| GET | `/assistant/recap/video/{video_id}` | List drafts for an owned video, newest first. |
| GET | `/assistant/recap/{draft_id}` | One draft. |

## Shorts

| Method | Route | Description |
| --- | --- | --- |
| POST | `/shorts/generate/{video_id}` | Detect highlight moments and queue a `shorts` job. Body: `{ count, clip_duration, aspect_ratio, burn_subtitles, subtitle_source, language? }`. Returns 201. |
| GET | `/shorts/video/{video_id}` | List generated clips for an owned video: `start_time`, `end_time`, `score`, `duration`. |
| GET | `/shorts/{clip_id}/download` | Download one clip as MP4. 302-redirects to a presigned URL when the clip was synced to object storage. |

## Transcripts

| Method | Route | Description |
| --- | --- | --- |
| POST | `/transcripts/start/{video_id}` | Queue a transcription job for an owned video. Returns 201. |
| GET | `/transcripts/{video_id}` | Get the transcript for an owned video. 404 when none exists yet. |

## Translations

| Method | Route | Description |
| --- | --- | --- |
| POST | `/translations` | Queue a translation. Body: `{ "video_id", "target_language" }`. Requires an existing transcript (409 otherwise); unsupported languages return 422. |
| GET | `/translations/video/{video_id}?target_language=<code>` | Get the translation for an owned video and language. 404 when none exists yet. |

## Dubbing

| Method | Route | Description |
| --- | --- | --- |
| GET | `/dubbings/providers` | List TTS providers (`edge`, `openai`). |
| GET | `/dubbings/voices?provider=<p>&language=<code>` | List voices for a provider/language. |
| POST | `/dubbings/preview` | Render a short sample. Body: `{ "text", "voice", "provider" }`. Returns `audio/mpeg`. |
| POST | `/dubbings/start/{video_id}` | Queue a dubbing job. Body: `{ "provider", "voice", "target_language" }` (all optional). Requires an existing transcript (409 otherwise); `target_language` requires an existing translation (409 otherwise). Returns 201. |

## Faces

| Method | Route | Description |
| --- | --- | --- |
| POST | `/faces/analyze/{video_id}` | Queue a `face_detection` job. Returns 201. Re-running replaces the previous analysis. |
| GET | `/faces/{video_id}` | Return the stored `FaceAnalysis` JSON (people with persistent person IDs, timestamps, and per-frame bounding boxes). 404 when no analysis exists. |

## Subtitles

| Method | Route | Description |
| --- | --- | --- |
| POST | `/subtitles/burn/{video_id}` | Burn subtitles into the video. Body: `{ "source": "transcript" \| "translation", "format": "ass" \| "srt", "language?" }`. 409 when the transcript (or the requested translation) is missing. Returns 201; the MP4 downloads from `GET /api/jobs/{job_id}/output`. |
