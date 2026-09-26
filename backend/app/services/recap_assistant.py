"""Recap script assistant: turn a transcript into a structured recap draft.

Calls the OpenAI Responses API with a strict JSON schema, the same way the
translation service does. The transcript is truncated to bound cost; the
response is validated before it is stored.
"""

import json
from collections.abc import Sequence

from app.core.config import OPENAI_API_KEY, RECAP_MODEL

# Keep prompts bounded: ~15k characters of transcript is plenty for a recap outline.
MAX_TRANSCRIPT_CHARS = 15_000

RECAP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titles", "hook", "beats", "key_quotes"],
    "properties": {
        "titles": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5,
            "description": "Catchy YouTube-style recap video title ideas.",
        },
        "hook": {
            "type": "string",
            "description": "A 2-3 sentence opening hook for the recap narration.",
        },
        "beats": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["timestamp", "heading", "summary"],
                "properties": {
                    "timestamp": {"type": "number", "description": "Start time in seconds."},
                    "heading": {"type": "string"},
                    "summary": {"type": "string",
                               "description": "2-4 sentences narrating this story beat."},
                },
            },
        },
        "key_quotes": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["timestamp", "text"],
                "properties": {
                    "timestamp": {"type": "number"},
                    "text": {"type": "string"},
                },
            },
        },
    },
}

INSTRUCTIONS = (
    "You are a movie-recap scriptwriter. The user pastes a video transcript with "
    "timestamps (seconds) and you produce a structured recap draft: catchy title ideas, "
    "an opening hook, story beats in chronological order (each with the timestamp where "
    "the beat starts and 2-4 sentences of narration), and up to 8 key quotes worth "
    "keeping verbatim. Narration should be vivid and spoiler-complete — this is a full "
    "recap, not a teaser. Return JSON only, exactly matching the provided schema."
)


def _transcript_payload(segments: Sequence[dict]) -> str:
    lines = []
    for segment in segments:
        start = float(segment.get("start", 0) or 0)
        text = str(segment.get("text", "")).strip()
        if text:
            lines.append(f"[{start:.1f}s] {text}")
    joined = "\n".join(lines)
    if len(joined) > MAX_TRANSCRIPT_CHARS:
        joined = joined[:MAX_TRANSCRIPT_CHARS] + "\n[truncated]"
    return joined


def generate_recap_draft(segments: Sequence[dict]) -> dict:
    """Generate a structured recap draft from transcript segments."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    payload = _transcript_payload(segments)
    if not payload.strip():
        raise RuntimeError("The transcript is empty; nothing to draft from")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai is not installed. Install the backend dependencies first.") from exc

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.responses.create(
        model=RECAP_MODEL,
        store=False,
        instructions=INSTRUCTIONS,
        input=payload,
        text={
            "format": {
                "type": "json_schema",
                "name": "recap_draft",
                "strict": True,
                "schema": RECAP_SCHEMA,
            },
        },
    )
    try:
        parsed = json.loads(response.output_text)
        if (not isinstance(parsed.get("titles"), list) or not parsed["titles"]
                or not isinstance(parsed.get("hook"), str) or not parsed["hook"].strip()
                or not isinstance(parsed.get("beats"), list) or not parsed["beats"]):
            raise ValueError("Response is missing required recap sections")
        for beat in parsed["beats"]:
            float(beat["timestamp"])  # must be numeric
        return parsed
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenAI returned an invalid recap draft") from exc
