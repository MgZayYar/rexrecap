"""Voice selection for dubbing.

Resolves a stable default voice per language/provider at runtime from the
provider's real voice list, so voice IDs never go stale. Deterministic:
Neural voices first, then gender match, then alphabetical.
"""

from __future__ import annotations

from app.ai.dubbing.providers import Voice, get_provider


def _rank(voice: Voice, gender: str | None) -> tuple[int, int, str]:
    neural = 0 if "neural" in voice.id.lower() else 1
    gender_match = 0 if (gender and voice.gender.lower() == gender.lower()) else 1
    return (neural, gender_match, voice.id)


async def resolve_voice(provider_name: str | None, language: str,
                        gender: str | None = None,
                        voice_id: str | None = None) -> Voice:
    """Return the requested voice, or the best default for the language."""
    provider = get_provider(provider_name)
    if voice_id:
        voices = await provider.list_voices()
        for voice in voices:
            if voice.id.lower() == voice_id.lower():
                return voice
        raise ValueError(f"Voice {voice_id!r} is not available from provider {provider.name!r}")
    candidates = await provider.list_voices(language)
    if not candidates:
        candidates = await provider.list_voices()
    if not candidates:
        raise RuntimeError(f"Provider {provider.name!r} returned no voices")
    return sorted(candidates, key=lambda v: _rank(v, gender))[0]


async def list_voices(provider_name: str | None, language: str | None = None) -> list[Voice]:
    return await get_provider(provider_name).list_voices(language)


async def resolve_speaker_voices(provider_name: str | None, language: str,
                                 voice_id: str | None = None) -> dict[str, Voice]:
    """Voices for speaker A (requested or default) and B (a different voice,
    preferring the opposite gender when the provider reports genders)."""
    voice_a = await resolve_voice(provider_name, language, voice_id=voice_id)
    provider = get_provider(provider_name)
    candidates = await provider.list_voices(language) or await provider.list_voices()
    others = [v for v in candidates if v.id.lower() != voice_a.id.lower()]
    if not others:
        return {"A": voice_a, "B": voice_a}
    if voice_a.gender:
        opposite = [v for v in others if v.gender and v.gender.lower() != voice_a.gender.lower()]
        pool = opposite or others
    else:
        pool = others
    voice_b = sorted(pool, key=lambda v: (0 if "neural" in v.id.lower() else 1, v.id))[0]
    return {"A": voice_a, "B": voice_b}
