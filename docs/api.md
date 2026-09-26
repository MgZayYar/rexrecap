# API

All routes are served under the canonical `/api/v1` prefix. The unversioned `/api` prefix serves the same routes for backward compatibility; new clients should use `/api/v1`.

Protected routes require `Authorization: Bearer <JWT>`. The Next.js frontend keeps the token in an HTTP-only cookie and attaches it in its backend-for-frontend handlers, so browser code never handles the token directly.

Errors are JSON: `{ "detail": "<message>" }`.

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
| DELETE | `/videos/uploads/{upload_id}` | Abort a session and delete the partial file. |
| GET | `/videos` | List the current user's videos. |
| PATCH | `/videos/{video_id}` | Assign, move, or unassign a video's project. Body: `{ "project_id": number | null }`; omitting the field leaves the assignment unchanged. 404 for a foreign project. |
| GET | `/videos/{video_id}/download` | Download an owned video. |
| GET | `/videos/{video_id}/playback` | Stream an owned video (supports `Range` requests). |

## Jobs

| Method | Route | Description |
| --- | --- | --- |
| POST | `/jobs/create` | Queue a processing job for an owned video. Body: `{ video_id, job_type, params? }`. |
| GET | `/jobs` | List the current user's jobs, newest first. Optional `status` and `video_id` filters. |
| GET | `/jobs/video/{video_id}` | List jobs for one owned video. |
| GET | `/jobs/{job_id}` | One owned job. |
| POST | `/jobs/{job_id}/cancel` | Cancel a job. Queued jobs stop immediately; a running job is aborted cooperatively at its next progress checkpoint. 409 for terminal jobs. |
| POST | `/jobs/{job_id}/retry` | Requeue a failed or cancelled job. 409 for anything else. |
| GET | `/jobs/{job_id}/output` | Download the job's output file. |
| GET | `/jobs/workers` | Worker heartbeats: `worker_id`, `started_at`, `last_seen`, `current_job_id`, and computed `is_live`. |

Job types: `transcription`, `translation`, `dubbing`, `autocrop`, `face_detection`, `subtitle_burn`, `render`, `shorts`. The `render` worker assembles the final delivery MP4 (`<uuid>_render.mp4`); the optional `params` object carries per-job options — the autocrop worker reads `params.aspect_ratio` (`"9:16"` default, also `"1:1"` and `"4:5"`), and the render worker reads `params.aspect_ratio` (smart-crop stage), `params.burn_subtitles` (`"ass"`/`"srt"`), `params.subtitle_source` (`"transcript"`/`"translation"`), `params.language`, and `params.use_dubbed_audio` (replaces the audio track with the video's latest completed dubbing output). Job responses include `has_output: true` when a download is available.

## Shorts

| Method | Route | Description |
| --- | --- | --- |
| POST | `/shorts/generate/{video_id}` | Detect highlight moments and queue a `shorts` job. Body: `{ count, clip_duration, aspect_ratio, burn_subtitles, subtitle_source, language? }`. Returns 201. |
| GET | `/shorts/video/{video_id}` | List generated clips for an owned video: `start_time`, `end_time`, `score`, `duration`. |
| GET | `/shorts/{clip_id}/download` | Download one clip as MP4. |

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
