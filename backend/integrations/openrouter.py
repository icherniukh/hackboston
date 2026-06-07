import base64
import json
import os
import random

from openrouter import OpenRouter

from backend.secrets import OPENROUTER_API_KEY

DEFAULT_MODEL = "google/gemma-4-31b-it"
IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"

SONG_PROMPT_SYSTEM_PROMPT = """You are a creative songwriter and music prompt engineer. Given a user's input message and a desired mood, you produce TWO things:

1. **lyrics**: Exactly 4 lines of the original hook lyrics that reflect the user's input message, and optionally mood and/or desired genre. If either mood or genre is not specified, derive it from the other two. If neither is specified, derive both from the input message.
2. **style_prompt**: A detailed text prompt suitable for feeding into an AI music generation model (e.g. Suno, Udio). Describe instrumentation, tempo, genre, vocal style, and atmosphere.

Always respond with valid JSON in this exact format:
{
  "lyrics": "<your lyrics here>",
  "style_prompt": "<your music generation prompt here>"
}

Do not include any text outside the JSON object."""

SONG_TITLE_SYSTEM_PROMPT = """You are a creative songwriter. Given a user's input message, condense it into a short, evocative song title of no more than 5 words. The title should capture the emotional essence of the message.

Always respond with valid JSON in this exact format:
{
  "title": "<your song title here>"
}

Do not include any text outside the JSON object."""

ALBUM_ART_SYSTEM_PROMPT = """You are an album art designer. Given a description of a song's theme and mood, generate a striking, evocative image suitable for album cover art. The image should visually capture the emotional essence of the song — its atmosphere, colors, and energy, while being intelligible when seen on a thumbnail. Do not include any text or words in the image."""

REPLY_CONTEXT_SYSTEM_PROMPT = """Given a snippet of song lyrics that was sent to you in place of a text message, generate a reply message pretending to be the intended recipient of the original. The reply should be emotionally or thematically connected — a counterpoint, echo, or answer to the original. Be playful but stay on theme.

Always respond with valid JSON in this exact format:
{
  "reply_message": "<your reply message here>"
}

Do not include any text outside the JSON object."""

GENRES = [
    # "hip-hop",
    "rock",
    # "pop",
    # "r&b",
    "edm",
    "jazz",
    "indie",
    "country",
    # "metal",
]


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(cleaned)


def generate_song_prompt(
    *,
    input_message: str,
    mood: str | None = None,
    genre: str | None = None,
    model: str | None = None,
) -> dict:
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
                {"role": "system", "content": SONG_PROMPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

    raw = res.choices[0].message.content
    parsed = _parse_json_response(raw)

    return {
        "lyrics": parsed.get("lyrics", ""),
        "style_prompt": parsed.get("style_prompt", ""),
    }


def generate_reply_context(*, original_lyrics: str, model: str | None = None) -> dict:
    model = model or DEFAULT_MODEL

    user_content = f"Original lyrics:\n{original_lyrics}"

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
        "genre": random.choice(GENRES),
    }


def generate_album_art(
    *,
    input_message: str,
    out_dir: str,
    model: str | None = None,
) -> str:
    model = model or IMAGE_MODEL

    user_content = f"Song theme: {input_message}"

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        res = client.chat.send(
            model=model,
            messages=[
                {"role": "system", "content": ALBUM_ART_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

    images = res.choices[0].message.images
    if not images:
        raise RuntimeError("No image in model response")

    url = images[0].image_url.url
    if url.startswith("data:"):
        _, b64 = url.split(",", 1)
        img_bytes = base64.b64decode(b64)
    else:
        import requests
        img_bytes = requests.get(url).content

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "cover.png")
    with open(path, "wb") as f:
        f.write(img_bytes)
    return path


def generate_song_title(*, input_message: str, model: str | None = None) -> str:
    model = model or DEFAULT_MODEL

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        res = client.chat.send(
            model=model,
            messages=[
                {"role": "system", "content": SONG_TITLE_SYSTEM_PROMPT},
                {"role": "user", "content": input_message},
            ],
        )

    raw = res.choices[0].message.content
    parsed = _parse_json_response(raw)
    return parsed.get("title", "")
