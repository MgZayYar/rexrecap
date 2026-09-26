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
| DELETE | `/projects/{project_id}` | Delete an owned project. Returns 204. |

## Videos

| Method | Route | Description |
| --- | --- | --- |
| POST | `/videos/upload` | Upload an owned MP4, MOV, MKV, or AVI file as multipart field `file`. Enforces the `MAX_UPLOAD_BYTES` limit (413 when exceeded). Returns 201. |
| GET | `/videos` | List the current user's videos. |
| GET | `/videos/{video_id}/download` | Download an owned video. |
| GET | `/videos/{video_id}/playback` | Stream an owned video (supports `Range` requests). |

## Jobs

| Method | Route | Description |
| --- | --- | --- |
| POST | `/jobs/create` | Queue a job. Body: `{ "video_id", "job_type", "params?" }`. Returns 201. |
| GET | `/jobs/video/{video_id}` | List jobs for an owned video, newest first. |
| GET | `/jobs/{job_id}` | Get one job (ownership-checked through its video). |
| GET | `/jobs/{job_id}/output` | Download the file a job produced (404 when the job has no output). |

Job types: `transcription`, `translation`, `dubbing`, `autocrop`, `face_detection`, `subtitle_burn`, `render`. The `render` worker assembles the final delivery MP4 (`<uuid>_render.mp4`); the optional `params` object carries per-job options — the autocrop worker reads `params.aspect_ratio` (`"9:16"` default, also `"1:1"` and `"4:5"`), and the render worker reads `params.aspect_ratio` (smart-crop stage), `params.burn_subtitles` (`"ass"`/`"srt"`), `params.subtitle_source` (`"transcript"`/`"translation"`), `params.language`, and `params.use_dubbed_audio` (replaces the audio track with the video's latest completed dubbing output). Job responses include `has_output: true` when a download is available.

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
