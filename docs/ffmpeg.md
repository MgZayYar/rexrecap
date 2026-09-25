# FFmpeg setup

RexCrop uses FFmpeg to extract a mono 16 kHz WAV track before Whisper inference.

## Install

Install an FFmpeg build for your operating system and make the `ffmpeg` executable available on `PATH`.

On Windows, one common approach is to install a trusted FFmpeg distribution, add its `bin` directory to the system or user `PATH`, then start a new terminal. Verify it with:

```powershell
ffmpeg -version
```

## Configure a custom path

If FFmpeg is not on `PATH`, add this to `backend/.env`:

```env
FFMPEG_BINARY=C:\path\to\ffmpeg.exe
```

When a transcription job starts, RexCrop runs FFmpeg with no video output, one audio channel, and a 16 kHz sample rate. Failures are recorded on the related processing job and displayed through the dashboard status component.
