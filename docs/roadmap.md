# Roadmap

## Current foundation

- Cookie-based JWT authentication
- Per-user video uploads (streamed, size-limited) and secure downloads
- SQLite metadata storage with Alembic migrations
- User-owned projects (videos not yet linked to projects)
- In-process processing-job queue and dashboard status polling
- Local Whisper transcription with FFmpeg audio extraction
- Transcript search and copy interface
- Timestamp-preserving translation via the OpenAI Responses API
- Browser-based subtitle editor with SRT/ASS export
- Real autocrop: face-tracked vertical 9:16 reframe with downloadable output (`GET /api/jobs/{id}/output`)
- Smart auto crop: 9:16 / 1:1 / 4:5 with speaker tracking, face priority, multi-speaker switching, and safe margins
- Subtitle burn: burn transcript/translation subtitles into the video (SRT or styled ASS) with FFmpeg/libass
- Face detection/tracking service: OpenCV Haar cascade + greedy centroid tracker with persistent person IDs; JSON result per video (`POST /api/faces/analyze/{video_id}`, `GET /api/faces/{video_id}`)
- Representative backend (pytest) and frontend (Vitest) test suites

## Next

- Add resumable uploads and per-user quotas.
- Highlight-clip shorts generation (scene/audio-moment detection → multiple vertical clips).
- Add object storage and background delivery for large media files.
- Add job cancellation, retry, observability, and notifications.
- Add organization/workspace roles and production deployment configuration.

## Later

- Advanced editing workflows (shorts generation, thumbnails).
- Multi-region deployment and usage billing.
