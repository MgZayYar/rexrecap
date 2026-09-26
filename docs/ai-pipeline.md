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

Translation shares the same queue and lifecycle contract. Dubbing is real (see below); the render worker assembles the final delivery MP4 (smart-crop + burned subtitles + dubbed audio, all optional) without changing the API.

## Autocrop (vertical reframe)

`POST /api/jobs/create` with `job_type: "autocrop"` now runs a real pipeline that produces a downloadable 9:16 MP4:

```text
API request
  → ProcessingJob (queued)
  → in-process queue
  → worker marks processing
  → ffprobe reads dimensions/fps/duration          (app/video/analyze.py)
  → OpenCV Haar cascade detects faces at ~2 fps   (app/ai/faces/detector.py)
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

## Smart auto crop (Phase 10)

The autocrop worker is now a smart crop pipeline covering 9:16, 1:1, and 4:5:

```text
API request (params: {"aspect_ratio": "1:1"})
  → ProcessingJob (queued, params stored)
  → worker: probe video
  → load the video's stored FaceAnalysis when one exists (Phase 9 tracking
    data: persistent person IDs, per-frame boxes) -- else detect faces live
  → app/video/smartcrop.py plans the trajectory:
      speaker tracking (dominant face per sampled frame)
      face priority (largest face wins)
      multi-speaker switching (challenger must be 40% larger for 2 samples)
      safe margins (dominant face kept fully inside with an 8% margin)
      smooth camera movement (exponential easing + moving average)
  → chunked FFmpeg crop for the chosen ratio (app/video/reframe.py)
  → output saved to storage/outputs/<uuid>_<ratio>.mp4
```

Key design points:

- `POST /api/jobs/create` accepts an optional `params` object; the autocrop
  worker reads `params.aspect_ratio` (default `"9:16"`, invalid values fail
  the job with a clear error).
- Reusing the stored `FaceAnalysis` means detection runs once per video and
  every crop format shares the same tracking data.
- The frontend Auto-crop button has an aspect-ratio selector (9:16 / 1:1 / 4:5).
- The old 9:16-only helpers (`vertical_crop_size`, `render_vertical`) remain
  as thin wrappers, so existing callers keep working.

## Subtitle burn (Phase 11)

`POST /api/subtitles/burn/{video_id}` queues a `subtitle_burn` job that renders subtitles permanently into the video:

```text
API request (body: {"source": "transcript"|"translation", "format": "ass"|"srt", "language"?})
  → 409 when the video has no transcript (or no translation for the language)
  → ProcessingJob (queued, params stored)
  → worker: read transcript/translation segments
  → app/video/subtitles.py builds an SRT or ASS document
      (ASS uses a bold white / dark-outline recap style)
  → FFmpeg libass filter burns the subtitles in (video re-encoded, audio copied)
  → output saved to storage/outputs/<uuid>_subtitled.mp4
  → job.output_path recorded, downloadable from GET /api/jobs/{job_id}/output
```

Key design points:

- No new files are uploaded: the subtitles come from the stored transcript or translation, so what you burn is what the editor exported from.
- The subtitle editor page has a "Burn subtitles" card (source, language, and format selectors) that calls this endpoint.
- Empty subtitle text and unknown formats fail fast with a clear error instead of producing a broken video.

## Face detection (tracking service)

`POST /api/faces/analyze/{video_id}` queues a `face_detection` job. The worker samples the video at ~2 fps, detects faces with the shared OpenCV cascade, and tracks them across frames with persistent person IDs (greedy centroid tracker in `app/ai/faces/tracker.py`). The JSON result is stored as the video's `FaceAnalysis` row and read back with `GET /api/faces/{video_id}`:

```json
{
  "video_id": 12,
  "result": {
    "width": 1280,
    "height": 720,
    "duration": 95.4,
    "sample_fps": 2.0,
    "frames_sampled": 190,
    "people_count": 2,
    "people": [
      {
        "person_id": 1,
        "first_seen": 0.5,
        "last_seen": 88.0,
        "detection_count": 175,
        "detections": [{"t": 0.5, "x": 412.0, "y": 210.0, "w": 96.0, "h": 96.0}]
      }
    ]
  }
}
```

Key design points:

- One row per video; re-running analysis replaces the previous result.
- Detection is the same shared implementation the autocrop uses, so both pipelines agree on what a "face" is.
- Coordinates are native frame pixels (`x, y, w, h`); person IDs are stable across frames within one analysis run.
- ID switches can occur when faces cross or leave the frame for a while — a documented v1 limitation of the greedy tracker, to be replaced by a proper MOT model later.
- Downstream features (smart auto crop, shorts) consume the stored JSON instead of re-running detection.

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
