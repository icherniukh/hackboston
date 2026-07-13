"""Thin client for fal.ai's ACE-Step text-to-music model.

Generates a short audio clip from lyrics/style and returns the path to the
downloaded file. Mirrors the return shape of
``backend.integrations.suno.generate_clip`` so callers can swap providers
without changing call sites.

Designed to be imported (see `generate_clip`) and also run from the CLI:

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

MODEL_ID = "fal-ai/ace-step"

# ACE-Step is billed per second generated, and the pipeline trims the clip
# after generation anyway (based on detected vocal bounds), so there's no
# benefit to requesting a long clip upfront.
DEFAULT_DURATION_SECONDS = 30


def generate_clip(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """Generate one audio clip via fal.ai's ACE-Step and download it.

    Returns the completed :class:`Clip`; the local file path is available on
    the returned object's ``path`` attribute.
    """
    arguments = {
        "tags": style or "",
        "lyrics": lyrics or "",
        "duration": duration or DEFAULT_DURATION_SECONDS,
    }

    def _on_queue_update(update):
        if on_status:
            on_status(type(update).__name__)

    result = fal_client.subscribe(
        MODEL_ID,
        arguments=arguments,
        on_queue_update=_on_queue_update,
    )

    audio = result["audio"]
    audio_url = audio["url"]

    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "ace_step.wav")
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

    clip = generate_clip(
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
