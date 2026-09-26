# Roadmap

## Current foundation

- Cookie-based JWT authentication
- Per-user video uploads (streamed, size-limited) and secure downloads
- SQLite metadata storage with Alembic migrations
- User-owned projects with videos linked to projects (nullable `project_id`, project pages in the UI)
- Standalone worker process (`python -m app.workers.runner`) with the database as the durable job queue, plus dashboard status polling
- Local Whisper transcription with FFmpeg audio extraction
- Transcript search and copy interface
- Timestamp-preserving translation via the OpenAI Responses API
- Browser-based subtitle editor with SRT/ASS export
- Real autocrop: face-tracked vertical 9:16 reframe with downloadable output (`GET /api/jobs/{id}/output`)
- Smart auto crop: 9:16 / 1:1 / 4:5 with speaker tracking, face priority, multi-speaker switching, and safe margins
- Subtitle burn: burn transcript/translation subtitles into the video (SRT or styled ASS) with FFmpeg/libass
- Face detection/tracking service: OpenCV Haar cascade + greedy centroid tracker with persistent person IDs; JSON result per video (`POST /api/faces/analyze/{video_id}`, `GET /api/faces/{video_id}`)
- AI voice dubbing: Edge TTS (default) or OpenAI TTS per transcript/translation segments, mixed over the original audio ducked to 15%
- Real render pipeline: composable assembly of smart-crop + burned subtitles + dubbed audio into one delivery MP4
- Resumable chunked uploads (server-confirmed offsets, automatic client resume) with a per-user storage quota (`USER_STORAGE_QUOTA_BYTES`, default 10 GB)
- Job cancellation (cooperative, at progress checkpoints) and retry, worker heartbeats with a live/offline dashboard badge, and a filterable jobs list
- Job notifications: per-user email (SMTP) and webhook alerts for job completed/failed/cancelled events, managed from /settings/notifications with pause/resume, delete, and send-test controls; the runner dispatches them after each terminal state (failures logged, never fail the job)
- Highlight-clip shorts generation: audio-energy + scene-change + speech-density scoring picks the top non-overlapping windows, each cut and smart-cropped to vertical (9:16/1:1/4:5) with optional burned subtitles (`POST /api/shorts/generate/{video_id}`, `GET /api/shorts/video/{video_id}`)
- Object storage delivery: S3-compatible backend (boto3) for job outputs and clips; the runner syncs finished outputs and the download endpoints 302-redirect to presigned URLs so large media never flows through the API (`STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_ENDPOINT_URL`, credentials via env)
- Representative backend (pytest) and frontend (Vitest) test suites

## Done (recent)

- Production deployment configuration: backend + frontend Dockerfiles, `docker-compose.yml` (api/worker/web, optional MinIO profile), unauthenticated `GET /health` probe with DB + storage checks, env-overridable storage dirs, SQLite WAL mode for concurrent api/worker writes, root `.env.example`, `docs/deployment.md` production checklist.

- Thumbnail generation: `thumbnails` worker extracts frames across the video and scores them by sharpness + face prominence; `/videos/[id]/thumbnails` picker page (generate, preview, use-as-thumbnail via `videos.thumbnail_path`); `GET /thumbnails/{id}/image` serves candidates; migration 0011.
- Batch processing: `batch_runs`/`batch_run_items` (migration 0012); `POST /batch/runs` queues one job type across up to 50 owned videos; `GET /batch/runs` + `/batch/runs/{id}` with derived progress summaries and per-video job status; `/batch` page with video checkboxes, job-type picker, live progress cards, and a dashboard Batch link.

- Recap assistant: `recap` worker turns a finished transcript into a structured draft (title ideas, hook, timestamped story beats, key quotes) via the OpenAI Responses API with a strict JSON schema; `/videos/[id]/assistant` page renders drafts with copy-script; `recap_drafts` table (migration 0013); 409 when no transcript; honest failure when `OPENAI_API_KEY` is unset.

- API reference: rewrote `docs/api.md` to cover every router (auth, health, projects, videos + resumable uploads, processing jobs, notifications, batch, thumbnails, recap assistant, shorts, transcripts, translations, dubbing, faces, subtitles), added `tests/test_openapi.py` proving the schema builds with unique operation IDs and both `/api/v1` + `/api` prefixes in parity.

- Performance: migration 0014 adds composite indexes `processing_jobs(video_id, created_at)` and `processing_jobs(status, created_at)` — verified via EXPLAIN QUERY PLAN that the per-video job list and the runner's oldest-queued claim both use them. `GET /jobs` now takes a bounded `limit` (default 100, max 500). Dashboard polling consolidated: one `/api/jobs` request every 3s replaces N per-row 2s pollers (JobStatus is now presentational; VideoJobActions triggers an immediate refresh after queueing).

## Next

- UI polish pass (loading states, empty states, error surfaces).

## Scoped out

- Organization/workspace roles: deliberately not built. RexCrop is a single-creator personal tool; multi-tenant roles would rewrite every ownership check in the API for no benefit to the actual workflow. If sharing ever becomes real, the natural seam is the per-route `*_user_id == current_user.id` ownership checks.

## Later

- Multi-region deployment and usage billing.
