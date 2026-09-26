"""Text-to-speech provider abstraction for dubbing.

Two providers ship: EdgeTTS (free, no API key, 100+ voices across 50+
languages -- the default) and OpenAI TTS (needs OPENAI_API_KEY, 6 voices).
New providers implement the TTSProvider protocol and register in PROVIDERS.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    language: str
    gender: str
    provider: str


class TTSProvider(Protocol):
    name: str

    async def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
        """Render `text` with `voice_id` to an audio file (mp3)."""
        ...

    async def list_voices(self, language: str | None = None) -> list[Voice]:
        """Voices for a language prefix like 'es' (None = all)."""
        ...


class EdgeTTSProvider:
    """Free Microsoft Edge TTS: no key, wide language coverage."""

    name = "edge"

    async def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
        import os

        import edge_tts

        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit proxy: aiohttp's websocket connect doesn't always pick up
        # proxy env vars on its own, but honors an explicit value.
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        communicate = edge_tts.Communicate(text, voice_id, proxy=proxy)
        await communicate.save(str(output_path))

    async def list_voices(self, language: str | None = None) -> list[Voice]:
        import edge_tts

        raw = await edge_tts.list_voices()
        voices = [
            Voice(
                id=item["ShortName"],
                name=item.get("FriendlyName", item["ShortName"]),
                language=(item.get("Locale") or "")[:2].lower(),
                gender=item.get("Gender", ""),
                provider=self.name,
            )
            for item in raw
        ]
        if language:
            prefix = language.lower()[:2]
            voices = [v for v in voices if v.language == prefix]
        return voices


class OpenAITTSProvider:
    """OpenAI TTS: 6 voices, any language, billed per character."""

    name = "openai"
    MODEL = "gpt-4o-mini-tts"
    VOICE_IDS = ("alloy", "echo", "fable", "onyx", "nova", "shimmer")

    async def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
        import asyncio

        from openai import OpenAI

        from app.core.config import OPENAI_API_KEY

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set; cannot use the OpenAI TTS provider")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _call() -> bytes:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.audio.speech.create(
                model=self.MODEL, voice=voice_id, input=text, response_format="mp3"
            )
            return response.content

        audio = await asyncio.to_thread(_call)
        output_path.write_bytes(audio)

    async def list_voices(self, language: str | None = None) -> list[Voice]:
        return [
            Voice(id=vid, name=vid.capitalize(), language=language or "mul",
                  gender="", provider=self.name)
            for vid in self.VOICE_IDS
        ]


PROVIDERS: dict[str, TTSProvider] = {
    "edge": EdgeTTSProvider(),
    "openai": OpenAITTSProvider(),
}


def get_provider(name: str | None) -> TTSProvider:
    provider = PROVIDERS.get((name or "edge").lower())
    if provider is None:
        raise ValueError(f"Unknown TTS provider: {name!r} (choose from {sorted(PROVIDERS)})")
    return provider
