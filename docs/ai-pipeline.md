# AI Pipeline

The first production-capable AI pipeline is local speech-to-text. It is activated by `POST /api/transcripts/start/{video_id}`.

```text
API request
  → ProcessingJob (queued)
  → in-process queue
  → worker marks processing
  → FFmpeg extracts mono 16 kHz WAV audio
  → faster-whisper transcribes locally
  → Transcript saved to SQLite
  → job marked completed
```

The worker reports progress at each major boundary. If extraction, model loading, inference, or database persistence fails, it marks the job `failed` and saves the error message.

## Local Whisper adapter

`app/ai/whisper/` is intentionally independent of API routes and worker control flow:

- `audio.py` invokes FFmpeg.
- `transcriber.py` lazily loads and runs `faster-whisper`.
- `models.py` contains transcription result types.

The default model is `base`, running on CPU with `int8` compute. Set `WHISPER_MODEL`, `WHISPER_DEVICE`, and `WHISPER_COMPUTE_TYPE` in `backend/.env` to tune quality and hardware usage.

Translation shares the same queue and lifecycle contract. Dubbing is real (see below); render remains a progress-only placeholder so its real implementation can be added without changing the API.

## Autocrop (vertical reframe)

`POST /api/jobs/create` with `job_type: "autocrop"` now runs a real pipeline that produces a downloadable 9:16 MP4:

```text
API request
  → ProcessingJob (queued)
  → in-process queue
  → worker marks processing
  → ffprobe reads dimensions/fps/duration          (app/video/analyze.py)
  → OpenCV Haar cascade detects faces at ~2 fps
  → smoothed horizontal crop trajectory, clamped to the frame
  → chunked FFmpeg crop (2 s chunks) + concat      (app/video/reframe.py)
  → output saved to storage/outputs/<uuid>_vertical.mp4
  → job.output_path recorded, job marked completed
```

Key design points:

- All FFmpeg invocations go through `app/video/ffmpeg.py:run_ffmpeg`; analysis never shells out elsewhere.
- Face detection uses the Haar cascade bundled with `opencv-python-headless` 4.x — no model download. (OpenCV 5.x removed `CascadeClassifier`, so the dependency is pinned to `<5.0`.)
- When no faces are found the crop stays centered; already-vertical videos keep their full frame.
- The trajectory is smoothed with a centered moving average so the virtual camera pans instead of jumping.
- Completed jobs expose `has_output: true` and the file downloads from `GET /api/jobs/{job_id}/output` (ownership-checked, path-traversal safe).

## Dubbing (AI voice-over)

`POST /api/dubbings/start/{video_id}` runs a real dubbing pipeline that produces a downloadable MP4 with AI-generated voice-over:

```text
API request (provider, voice, optional target_language)
  → ProcessingJob (queued, params stored on the job)
  → in-process queue
  → worker marks processing
  → transcript (or translation) segments loaded      (speaker turns below)
  → pause gaps > 1.5 s split segments into speaker turns A/B
  → voices resolved per speaker (provider catalog)  (app/ai/dubbing/voices.py)
  → each segment synthesized to mp3, concurrency 4  (app/ai/dubbing/providers.py)
  → dubs delayed to their timestamps, mixed over the
    original audio ducked to 15% (music preserved)   (app/ai/dubbing/audio.py)
  → video stream copied, audio re-encoded to AAC
  → output saved to storage/outputs/<uuid>_dubbed.mp4
  → job.output_path recorded, job marked completed
```

Key design points:

- Two TTS providers behind a protocol (`TTSProvider`): **Edge TTS** (default — free, no API key, 100+ voices across 50+ languages) and **OpenAI TTS** (`gpt-4o-mini-tts`, needs `OPENAI_API_KEY`). New providers register in `PROVIDERS`.
- Voice IDs are resolved at runtime from the provider's real voice list, so they never go stale; speaker B automatically gets a contrasting voice (opposite gender when the provider reports genders).
- Dubbing the transcript's own language is the default; pass `target_language` to dub an existing translation instead.
- A transcript is required first (409 otherwise); each segment is synthesized in the target language as-is, so the dub follows the original timing.
- Known v1 limitations: TTS longer than its segment overlaps the next one rather than being time-stretched; speaker turns come from pause gaps, not neural diarization. Both are documented for a later upgrade.
- Voice preview (`POST /api/dubbings/preview`) renders up to 300 characters so the user can hear a voice before committing to a full dub.
