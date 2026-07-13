"""Thin client for the Suno public API.

Generates a short audio clip from lyrics / style / mood and returns the path to
the downloaded file. The Suno API is asynchronous (submit -> poll -> download)
and has no native "length" parameter, so a target length is honoured by
trimming the finished clip locally with ffmpeg.

Designed to be imported (see `generate_clip`) and also run from the CLI:

    python -m backend.suno --description "upbeat synthwave about Tokyo at night"
    python -m backend.suno --lyrics "[Verse]..." --style "dreampop" --length 20
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

import requests

from backend.integrations.ffmpeg import trim
from backend.integrations.music_types import Clip
from backend.secrets import SUNO_API_KEY

BASE_URL = "https://api.suno.com"

# Preset voices from the Suno docs. Custom voice cloning is not open to partners.
PRESET_VOICES = {
    "female": "5b915c6d-8d96-416c-9755-eba65868cfef",  # Preset voice A
    "kid": "c036ce3a-55e4-4690-9b8d-4516b37a96d5",  # Preset voice B (weird kid voice)
    "male": "27f5465b-73c3-4134-b11e-70b0bd571c6c",  # Preset voice C (low male voice)
}

# Terminal poll states.
_DONE = {"complete", "error"}


class SunoError(RuntimeError):
    """Raised when the Suno API returns an error or a job fails."""


class SunoClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {SUNO_API_KEY}",
                "Content-Type": "application/json",
            }
        )

    # -- low-level ---------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict:
        resp = self.session.post(
            f"{self.base_url}{path}", json=payload, timeout=self.timeout
        )
        return self._unwrap(resp)

    def _get(self, path: str) -> dict:
        resp = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        return self._unwrap(resp)

    @staticmethod
    def _unwrap(resp: requests.Response) -> dict:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400:
            msg = body.get("error") or resp.text or resp.reason
            raise SunoError(f"Suno API {resp.status_code}: {msg}")
        return body

    # -- generation --------------------------------------------------------

    def submit(
        self,
        *,
        lyrics: Optional[str] = None,
        style: Optional[str] = None,
        description: Optional[str] = None,
        mood: Optional[str] = None,
        title: Optional[str] = None,
        voice_id: Optional[str] = None,
        instrumental: bool = False,
    ) -> str:
        """Submit a generation job and return its clip id.

        Two modes (per the docs, they are mutually exclusive):
          * Simple  -> pass ``description`` (model writes lyrics + style)
          * Custom  -> pass ``lyrics`` and/or ``style``

        ``mood`` is not a native Suno field; it is folded into the style (custom
        mode) or the description (simple mode) so callers can pass it cleanly.
        """
        if description and style:
            raise SunoError("Pass either `description` or `style`, not both.")

        payload: dict = {}

        if mood:
            if description:
                description = f"{description}, {mood} mood"
            else:
                style = f"{style}, {mood}" if style else mood

        if description:
            payload["description"] = description
        if lyrics:
            payload["lyrics"] = lyrics
        if style:
            payload["style"] = style
        if title:
            payload["title"] = title
        if voice_id:
            payload["voice_id"] = self._resolve_voice(voice_id)
        if instrumental:
            payload["instrumental"] = True

        if not instrumental and not (description or lyrics):
            raise SunoError(
                "Provide `description` (simple mode), `lyrics`/`style` (custom "
                "mode), or set instrumental=True."
            )

        body = self._post("/v0/audio", payload)
        clip_id = body.get("id")
        if not clip_id:
            raise SunoError(f"No clip id in response: {body}")
        return clip_id

    @staticmethod
    def _resolve_voice(voice_id: str) -> str:
        """Allow friendly names (female/kid/male) or a raw UUID."""
        return PRESET_VOICES.get(voice_id.lower(), voice_id)

    def poll(
        self,
        clip_id: str,
        *,
        interval: float = 3.0,
        timeout: float = 300.0,
        on_status=None,
    ) -> Clip:
        """Poll a clip until it is complete (or errors / times out)."""
        deadline = time.monotonic() + timeout
        last_status = None
        while True:
            body = self._get(f"/v0/audio/{clip_id}")
            status = body.get("status", "unknown")
            if on_status and status != last_status:
                on_status(status)
            last_status = status

            if status == "complete":
                return Clip(
                    id=clip_id,
                    status=status,
                    audio_url=body.get("audio_url", ""),
                    title=body.get("title"),
                    raw=body,
                )
            if status == "error":
                raise SunoError(f"Generation failed: {body.get('error')}")
            if time.monotonic() >= deadline:
                raise SunoError(
                    f"Timed out after {timeout}s (last status: {status})."
                )
            time.sleep(interval)

    # -- download / trim ---------------------------------------------------

    def download(self, url: str, dest: str) -> str:
        resp = self.session.get(url, timeout=self.timeout, stream=True)
        if resp.status_code >= 400:
            raise SunoError(f"Failed to download audio: HTTP {resp.status_code}")
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)
        return dest


def generate_clip(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    description: Optional[str] = None,
    title: Optional[str] = None,
    voice_id: Optional[str] = None,
    instrumental: bool = False,
    poll_interval: float = 3.0,
    poll_timeout: float = 300.0,
    on_status=None,
) -> Clip:
    """Generate one audio clip end to end and download it.

    Returns the completed :class:`Clip`; the local file path is available on the
    returned object's ``path`` attribute (set below). If ``length`` is given, the
    downloaded clip is trimmed to that many seconds with ffmpeg.
    """
    client = SunoClient()
    clip_id = client.submit(
        lyrics=lyrics,
        style=style,
        description=description,
        title=title,
        voice_id=voice_id,
        instrumental=instrumental,
    )
    clip = client.poll(
        clip_id,
        interval=poll_interval,
        timeout=poll_timeout,
        on_status=on_status,
    )
    if not clip.audio_url:
        raise SunoError("Clip completed but no audio_url was returned.")

    os.makedirs(out_dir, exist_ok=True)
    clip.path = client.download(clip.audio_url, f"{os.path.join(out_dir, 'suno')}.mp3")

    return clip


# -- CLI -------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="suno",
        description="Generate a short audio clip with the Suno API.",
    )
    p.add_argument("--lyrics", help="Your own lyrics (custom mode).")
    p.add_argument("--style", help="Style string, e.g. 'dreampop, melancholic'.")
    p.add_argument(
        "--description",
        help="Natural-language prompt (simple mode). Mutually exclusive with --style.",
    )
    p.add_argument("--mood", help="Mood, folded into style/description.")
    p.add_argument("--title", help="Optional track title.")
    p.add_argument(
        "--voice",
        dest="voice_id",
        help="Preset voice: female | kid | male, or a raw voice UUID.",
    )
    p.add_argument(
        "--instrumental", action="store_true", help="Generate without vocals."
    )
    p.add_argument(
        "--length",
        type=float,
        help="Trim the result to this many seconds (uses ffmpeg).",
    )
    p.add_argument(
        "--out-dir", default=".", help="Directory for the downloaded file."
    )
    p.add_argument(
        "--poll-timeout",
        type=float,
        default=300.0,
        help="Max seconds to wait for completion (default 300).",
    )
    return p


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)

    def on_status(status: str) -> None:
        print(f"  status: {status}", file=sys.stderr)

    try:
        clip = generate_clip(
            lyrics=args.lyrics,
            style=args.style,
            description=args.description,
            title=args.title,
            voice_id=args.voice_id,
            instrumental=args.instrumental,
            out_dir=args.out_dir,
            poll_timeout=args.poll_timeout,
            on_status=on_status,
        )
    except SunoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {clip.path}")
    print(f"  id:    {clip.id}")
    print(f"  title: {clip.title}")
    print(f"  url:   {clip.audio_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
