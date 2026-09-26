# RexCrop — Release Notes

RexCrop is Rexzee's personal movie-recap workstation: upload a film, get a
transcript, translate and dub it, cut shorts and thumbnails, burn subtitles,
render the final vertical delivery, and draft the recap script — all from one
dashboard.

## What it does today

- **Ingest** — single-shot and resumable chunked uploads (8 MB chunks, offset
  recovery), per-user storage quota, project organization.
- **Transcribe & translate** — Whisper transcription with searchable
  timestamped segments; 60+ target languages for translation.
- **Dubbing** — Edge TTS (free, no key) and OpenAI TTS, speaker-aware mixing
  over ducked original audio.
- **Reframe** — face-tracked 9:16 / 1:1 / 4:5 smart-crop, subtitle burn
  (ASS/SRT), composable render pipeline.
- **Shorts** — energy + scene-change highlight detection, vertical clip
  export with shifted subtitles.
- **Thumbnails** — sharpness + face-prominence candidate scoring, pick and
  set the video thumbnail.
- **Recap assistant** — OpenAI-powered draft: title ideas, hook,
  timestamped story beats, key quotes. Requires `OPENAI_API_KEY`.
- **Batch** — queue one job type across up to 50 videos with live progress.
- **Ops** — standalone worker process, job cancel/retry, worker
  heartbeats, email/webhook notifications, S3-compatible output delivery,
  Docker Compose deployment, full OpenAPI reference (`docs/api.md`).

## Verified 2026-09-26

End-to-end against the real API and the real standalone worker (fresh
database, migrations 0001–0014): register → login → upload → autocrop job →
vertical 202×360 MP4 download; batch of 2 thumbnail jobs → summary flips to
completed with 8 candidates; `/health` and `/openapi.json` live. 151 backend
tests, frontend typecheck / ESLint / Vitest / production build all green.

## Honest caveats

- The recap assistant's live OpenAI call was not executed here (no API key
  in this environment, and no spend without approval). The prompt, strict
  JSON schema, parsing, and validation path are real code, covered by tests
  with a fake client; it fails loudly when `OPENAI_API_KEY` is unset.
- Docker images were not built here (no Docker daemon); Dockerfiles and
  Compose config are validated syntactically.
- The Edge TTS websocket could not be tested from this sandbox (egress
  proxy breaks the upgrade); the dubbing pipeline is verified end-to-end
  with offline TTS.
