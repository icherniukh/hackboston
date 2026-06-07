import json
import random

from openrouter import OpenRouter

from backend.secrets import OPENROUTER_API_KEY

DEFAULT_MODEL = "google/gemma-4-31b-it:free"

MOODS = [
    "happy", "sad", "melancholic", "upbeat", "dreamy",
    "aggressive", "chill", "nostalgic", "hopeful", "dark",
]
GENRES = [
    "pop", "rock", "hip-hop", "r&b", "electronic", "folk",
    "jazz", "indie", "ambient", "country", "soul", "punk",
]

REPLY_CONTEXT_SYSTEM_PROMPT = """You are a creative songwriter. Given an original message that inspired a song and its resulting lyrics, generate a reply message as if another person is responding to the original. The reply should be emotionally or thematically connected — a counterpoint, echo, or answer to the original.

Always respond with valid JSON in this exact format:
{
  "reply_message": "<your reply message here>"
}

Do not include any text outside the JSON object."""


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(cleaned)

SYSTEM_PROMPT = """You are a creative songwriter and music prompt engineer. Given a user's input message and a desired mood, you produce TWO things:

1. **lyrics**: Exactly 4 lines of the original hook lyrics that reflect the user's input message, and optionally mood and/or desired genre. If either mood or genre is not specified, derive it from the other two. If neither is specified, derive both from the input message.
2. **style_prompt**: A detailed text prompt suitable for feeding into an AI music generation model (e.g. Suno, Udio). Describe instrumentation, tempo, genre, vocal style, and atmosphere.

Always respond with valid JSON in this exact format:
{
  "lyrics": "<your lyrics here>",
  "style_prompt": "<your music generation prompt here>"
}

Do not include any text outside the JSON object."""


def generate_song_prompt(*, input_message: str, mood: str | None, genre: str | None, model: str | None = None) -> dict:
    model = model or DEFAULT_MODEL

    user_content = "\n".join([
        f"Input message: {input_message}",
        *([f"Mood: {mood}"] if mood else []),
        *([f"Genre: {genre}"] if genre else []),
    ])

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        res = client.chat.send(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

    raw = res.choices[0].message.content
    parsed = _parse_json_response(raw)

    return {
        "lyrics": parsed.get("lyrics", ""),
        "style_prompt": parsed.get("style_prompt", ""),
    }


def generate_reply_context(
    original_input_message: str, original_prompt: dict, model: str | None = None
) -> dict:
    model = model or DEFAULT_MODEL

    user_content = "\n".join([
        f"Original message: {original_input_message}",
        f"Original lyrics:\n{original_prompt['lyrics']}",
    ])

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        res = client.chat.send(
            model=model,
            messages=[
                {"role": "system", "content": REPLY_CONTEXT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

    raw = res.choices[0].message.content
    parsed = _parse_json_response(raw)

    return {
        "input_message": parsed.get("reply_message", ""),
        "mood": random.choice(MOODS),
        "genre": random.choice(GENRES),
    }
