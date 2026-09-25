import json
from collections.abc import Sequence

from app.core.config import OPENAI_API_KEY, TRANSLATION_MODEL


def translate_segment_batch(source_language: str, target_language: str, segments: Sequence[dict[str, object]]) -> list[str]:
    """Translate one batch while keeping segment identity outside the model response."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai is not installed. Install the backend dependencies first.") from exc

    payload = [{"id": index, "text": str(segment["text"])} for index, segment in enumerate(segments)]
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.responses.create(
        model=TRANSLATION_MODEL,
        store=False,
        instructions=(
            "You are a precise audiovisual translator. Translate from "
            f"{source_language or 'the detected source language'} to {target_language}. "
            "Return JSON only with this exact shape: {\"translations\":[{\"id\":0,\"text\":\"...\"}]}. "
            "Return one item per input id, retain ids, and translate only the text without commentary."
        ),
        input=json.dumps({"segments": payload}, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "segment_translations",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["translations"],
                    "properties": {
                        "translations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["id", "text"],
                                "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
                            },
                        },
                    },
                },
            },
        },
    )
    try:
        parsed = json.loads(response.output_text)
        by_id = {item["id"]: item["text"].strip() for item in parsed["translations"]}
        if set(by_id) != set(range(len(payload))) or not all(by_id.values()):
            raise ValueError("Response did not include every translated segment")
        return [by_id[index] for index in range(len(payload))]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenAI returned an invalid translation response") from exc
