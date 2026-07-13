"""Thin clients for fal.ai's music-generation models.

Each `generate_*` function takes the same standardized shape
(`out_dir`, `lyrics`, `style`, `duration`, `on_status`) and returns a `Clip`,
mirroring `backend.integrations.suno.generate_clip` so callers can swap
providers/models without changing call sites. Under the hood each function
builds the arguments its specific model's schema actually expects — some
models (ACE-Step, MiniMax) have a dedicated lyrics field; others (Lyria 3,
ElevenLabs Music, ACE-Step's prompt-to-audio variant) don't, so the lyrics
get folded into the style prompt instead of being force-fit into a
nonexistent field.

Designed to be imported and also run from the CLI:

    python -m backend.integrations.fal_music --lyrics "[Verse]..." --style "dreampop"
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

import fal_client
import requests

from backend.integrations.music_types import Clip
from backend.secrets import FAL_API_KEY

os.environ.setdefault("FAL_KEY", FAL_API_KEY)

# fal.ai is billed per second/generation, and the pipeline trims the clip
# after generation anyway (based on detected vocal bounds), so there's no
# benefit to requesting a long clip upfront.
DEFAULT_DURATION_SECONDS = 30


def _blend_lyrics_into_prompt(style: Optional[str], lyrics: Optional[str]) -> str:
    """For models with no dedicated lyrics field: fold the hook into the prompt."""
    prompt = style or ""
    if lyrics:
        prompt = f"{prompt} Vocal hook lyrics: {lyrics}".strip()
    return prompt


def _run(model_id: str, arguments: dict, *, out_dir: str, filename_stem: str, on_status=None) -> Clip:
    def _on_queue_update(update):
        if on_status:
            on_status(type(update).__name__)

    result = fal_client.subscribe(model_id, arguments=arguments, on_queue_update=_on_queue_update)

    audio = result.get("audio") or result.get("audio_file")
    audio_url = audio["url"]
    ext = ".wav" if audio.get("content_type", "").endswith("wav") else ".mp3"

    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, f"{filename_stem}{ext}")
    resp = requests.get(audio_url, timeout=60, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)

    return Clip(
        id=str(result.get("seed", "")),
        status="complete",
        audio_url=audio_url,
        path=dest,
        raw=result,
    )


def generate_ace_step(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fal-ai/ace-step — dedicated `tags` + `lyrics` + `duration` fields."""
    arguments = {
        "tags": style or "",
        "lyrics": lyrics or "",
        "duration": duration or DEFAULT_DURATION_SECONDS,
    }
    return _run("fal-ai/ace-step", arguments, out_dir=out_dir, filename_stem="ace_step", on_status=on_status)


# Back-compat alias — this was the only model this module supported before
# other fal.ai models were wired in.
generate_clip = generate_ace_step


def generate_ace_step_prompt_to_audio(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fal-ai/ace-step/prompt-to-audio — single `prompt` field, no lyrics field."""
    arguments = {
        "prompt": _blend_lyrics_into_prompt(style, lyrics),
        "duration": duration or DEFAULT_DURATION_SECONDS,
        "instrumental": not bool(lyrics),
    }
    return _run(
        "fal-ai/ace-step/prompt-to-audio", arguments, out_dir=out_dir,
        filename_stem="ace_step_prompt", on_status=on_status,
    )


def generate_minimax_v2(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fal-ai/minimax-music/v2 — `prompt` + dedicated `lyrics_prompt` field. No duration control."""
    arguments = {"prompt": style or ""}
    if lyrics:
        arguments["lyrics_prompt"] = lyrics
    return _run(
        "fal-ai/minimax-music/v2", arguments, out_dir=out_dir,
        filename_stem="minimax_v2", on_status=on_status,
    )


def _generate_minimax_vnext(model_id: str, filename_stem: str, *, out_dir, lyrics, style, on_status) -> Clip:
    """Shared body for v2.5/v2.6, which have identical `prompt`+`lyrics`+`is_instrumental` schemas."""
    arguments = {"prompt": style or "", "is_instrumental": not bool(lyrics)}
    if lyrics:
        arguments["lyrics"] = lyrics
    return _run(model_id, arguments, out_dir=out_dir, filename_stem=filename_stem, on_status=on_status)


def generate_minimax_v25(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fal-ai/minimax-music/v2.5 — `prompt` + `lyrics` + `is_instrumental`. No duration control."""
    return _generate_minimax_vnext(
        "fal-ai/minimax-music/v2.5", "minimax_v25",
        out_dir=out_dir, lyrics=lyrics, style=style, on_status=on_status,
    )


def generate_minimax_v26(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fal-ai/minimax-music/v2.6 — `prompt` + `lyrics` + `is_instrumental`. No duration control."""
    return _generate_minimax_vnext(
        "fal-ai/minimax-music/v2.6", "minimax_v26",
        out_dir=out_dir, lyrics=lyrics, style=style, on_status=on_status,
    )


def generate_lyria3(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fal-ai/lyria3 — single `prompt` field, no lyrics field, no duration control (fixed ~30s)."""
    arguments = {"prompt": _blend_lyrics_into_prompt(style, lyrics)}
    return _run("fal-ai/lyria3", arguments, out_dir=out_dir, filename_stem="lyria3", on_status=on_status)


def generate_elevenlabs(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fal-ai/elevenlabs/music — `prompt` + `music_length_ms`, no lyrics field."""
    arguments = {
        "prompt": _blend_lyrics_into_prompt(style, lyrics),
        "music_length_ms": int((duration or DEFAULT_DURATION_SECONDS) * 1000),
        "force_instrumental": not bool(lyrics),
    }
    return _run("fal-ai/elevenlabs/music", arguments, out_dir=out_dir, filename_stem="elevenlabs", on_status=on_status)


# -- CLI -------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fal_music",
        description="Generate a short audio clip with fal.ai's ACE-Step model.",
    )
    p.add_argument("--lyrics", help="Lyrics to sing, e.g. '[Verse]\\n...'.")
    p.add_argument(
        "--style", help="Comma-separated genre tags, e.g. 'dreampop, melancholic'."
    )
    p.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_SECONDS,
        help=f"Length of the generated clip in seconds (default {DEFAULT_DURATION_SECONDS}).",
    )
    p.add_argument(
        "--out-dir", default=".", help="Directory for the downloaded file."
    )
    return p


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)

    def on_status(status: str) -> None:
        print(f"  status: {status}", file=sys.stderr)

    clip = generate_ace_step(
        lyrics=args.lyrics,
        style=args.style,
        duration=args.duration,
        out_dir=args.out_dir,
        on_status=on_status,
    )

    print(f"Saved: {clip.path}")
    print(f"  id:  {clip.id}")
    print(f"  url: {clip.audio_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
