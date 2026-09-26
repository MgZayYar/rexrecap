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

Translation and dubbing handlers remain progress-only placeholders, as does render. They share the same queue and lifecycle contract so their real implementations can be added without changing the API.

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
