"""Multimodal LLM judge: score lyric fidelity + style adherence from the audio."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Optional

import requests

from backend.eval.store import (
    build_summary,
    list_clip_metas,
    resolve_run_dir,
    save_judge,
    utc_now,
)
from backend.integrations.openrouter import _parse_json_response
from backend.secrets import OPENROUTER_API_KEY

# Gemini Flash handles audio input well and is cheap enough for batch judging.
DEFAULT_JUDGE_MODEL = "google/gemini-2.5-flash"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT_S = 180

JUDGE_SYSTEM = """You are an expert evaluator for short AI-generated song clips used as playful iMessage-style replies.

You will hear one audio clip and receive:
- the original chat message that inspired it
- the intended lyrics (what should be sung)
- the intended style / production brief (genre, instrumentation, vocal character, mood)

Score the clip on these axes (integers 1–5):

1. lyrics_fidelity — Do the sung/spoken words match the intended lyrics?
   5 = clearly the intended lines (minor pronunciation OK)
   3 = partial / paraphrased / missing lines
   1 = different words, instrumental-only, or unintelligible mush
2. style_adherence — Does the music match the intended style brief?
   5 = genre, energy, and vocal character clearly match
   3 = vaguely related
   1 = clearly wrong genre/mood/vocal approach
3. style_bleed — Did the model sing style/production instructions as if they were lyrics?
   5 = no bleed (lyrics stay lyrics; style stays music)
   3 = some production jargon audible in vocals
   1 = sings the style brief / genre tags / BPM / instrumentation words
4. hook_fit — As a short sendable hook reacting to the original message, how well does it work?
   5 = instantly feels like a musical reply to that text
   3 = generic but usable
   1 = mismatch or unusable

Also provide:
- heard_lyrics: what you believe was sung (best-effort transcript)
- style_notes: short note on genre/mood/vocal vs the brief
- overall: integer 1–5 overall quality for this product use case
- rationale: 2–4 sentences

Respond with ONLY valid JSON:
{
  "scores": {
    "lyrics_fidelity": <1-5>,
    "style_adherence": <1-5>,
    "style_bleed": <1-5>,
    "hook_fit": <1-5>,
    "overall": <1-5>
  },
  "heard_lyrics": "<transcript>",
  "style_notes": "<notes>",
  "rationale": "<text>"
}
"""


def _audio_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in {"mp3", "wav", "m4a", "ogg", "flac", "aac", "aiff"}:
        return ext
    if ext == "mpeg":
        return "mp3"
    return "wav"


def _encode_audio(path: str) -> tuple[str, str]:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return data, _audio_format(path)


def judge_clip(
    *,
    audio_path: str,
    input_message: str,
    lyrics: str,
    style_prompt: str,
    genre: Optional[str] = None,
    model: str = DEFAULT_JUDGE_MODEL,
) -> dict[str, Any]:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is empty; cannot run LLM judge.")

    b64, fmt = _encode_audio(audio_path)
    user_text = "\n".join([
        f"Original message: {input_message}",
        f"Intended lyrics:\n{lyrics or '(none / instrumental)'}",
        f"Intended style brief:\n{style_prompt or '(none provided)'}",
        *([f"Genre pill: {genre}"] if genre else []),
        "",
        "Listen to the attached audio and score it per the system instructions.",
    ])

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": b64, "format": fmt},
                    },
                ],
            },
        ],
    }
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT_S,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenRouter judge HTTP {resp.status_code}: {resp.text[:800]}")

    body = resp.json()
    try:
        raw = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected OpenRouter response: {body}") from e

    if isinstance(raw, list):
        # Some multimodal responses return content parts.
        raw = "".join(part.get("text", "") for part in raw if isinstance(part, dict))

    parsed = _parse_json_response(raw)
    return {
        "judge_model": model,
        "judged_at": utc_now(),
        "raw_response": raw,
        "scores": parsed.get("scores", {}),
        "heard_lyrics": parsed.get("heard_lyrics", ""),
        "style_notes": parsed.get("style_notes", ""),
        "rationale": parsed.get("rationale", ""),
    }


def judge_run(
    run_dir: str,
    *,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    force: bool = False,
) -> dict:
    run_dir = resolve_run_dir(run_dir)
    metas = list_clip_metas(run_dir)
    print(f"Judging {len(metas)} clips in {run_dir}")

    for meta in metas:
        clip_id = meta["clip_id"]
        judge_path = os.path.join(run_dir, "clips", clip_id, "judge.json")
        if os.path.isfile(judge_path) and not force:
            print(f"  skip {clip_id} (already judged)")
            continue
        if meta.get("error") or not meta.get("audio_path"):
            judgment = {
                "judge_model": judge_model,
                "judged_at": utc_now(),
                "error": meta.get("error") or "missing audio",
                "scores": {},
            }
            save_judge(run_dir, clip_id, judgment)
            print(f"  skip-error {meta['music_model']} | {meta['message_id']}")
            continue

        audio_abs = os.path.join(run_dir, meta["audio_path"])
        try:
            judgment = judge_clip(
                audio_path=audio_abs,
                input_message=meta["input_message"],
                lyrics=meta.get("lyrics") or "",
                style_prompt=meta.get("style_prompt") or "",
                genre=meta.get("genre"),
                model=judge_model,
            )
            save_judge(run_dir, clip_id, judgment)
            scores = judgment.get("scores", {})
            print(
                f"  ok {meta['music_model']} | {meta['message_id']} | {meta['style_id']} "
                f"→ lyrics={scores.get('lyrics_fidelity')} style={scores.get('style_adherence')} "
                f"bleed={scores.get('style_bleed')} overall={scores.get('overall')}"
            )
        except Exception as e:
            save_judge(run_dir, clip_id, {
                "judge_model": judge_model,
                "judged_at": utc_now(),
                "error": f"{type(e).__name__}: {e}",
                "scores": {},
            })
            print(f"  ERROR {clip_id}: {e}")

    return build_summary(run_dir)
