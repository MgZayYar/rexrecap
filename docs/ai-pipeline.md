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

Translation, dubbing, autocrop, and render handlers remain progress-only placeholders. They share the same queue and lifecycle contract so their real implementations can be added without changing the API.
