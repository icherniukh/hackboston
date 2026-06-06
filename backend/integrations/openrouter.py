import json
from openrouter import OpenRouter

from backend.secrets import OPENROUTER_API_KEY

DEFAULT_MODEL = "google/gemma-4-31b-it:free"

SYSTEM_PROMPT = """You are a creative songwriter and music prompt engineer. Given a user's input message and a desired mood, you produce TWO things:

1. **lyrics**: Exactly 4 lines of the original hook lyrics that reflect the user's input message and mood.
2. **style_prompt**: A detailed text prompt suitable for feeding into an AI music generation model (e.g. Suno, Udio). Describe instrumentation, tempo, genre, vocal style, and atmosphere.

Always respond with valid JSON in this exact format:
{
  "lyrics": "<your lyrics here>",
  "style_prompt": "<your music generation prompt here>"
}

Do not include any text outside the JSON object."""


def generate_song_prompt(*, input_message: str, mood: str, model: str | None = None) -> dict:
    model = model or DEFAULT_MODEL

    user_content = f"Input message: {input_message}\nMood: {mood}"

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        res = client.chat.send(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

    raw = res.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)

    return {
        "lyrics": parsed.get("lyrics", ""),
        "style_prompt": parsed.get("style_prompt", ""),
    }
