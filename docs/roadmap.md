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
- Highlight-clip shorts generation: audio-energy + scene-change + speech-density scoring picks the top non-overlapping windows, each cut and smart-cropped to vertical (9:16/1:1/4:5) with optional burned subtitles (`POST /api/shorts/generate/{video_id}`, `GET /api/shorts/video/{video_id}`)
- Object storage delivery: S3-compatible backend (boto3) for job outputs and clips; the runner syncs finished outputs and the download endpoints 302-redirect to presigned URLs so large media never flows through the API (`STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_ENDPOINT_URL`, credentials via env)
- Representative backend (pytest) and frontend (Vitest) test suites

## Next

- Add job notifications (email/webhook) for completed and failed jobs.
- Add organization/workspace roles and production deployment configuration.

## Later

- Advanced editing workflows (thumbnails).
- Multi-region deployment and usage billing.
