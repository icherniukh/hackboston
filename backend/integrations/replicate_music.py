"""Thin client for Replicate-hosted music-generation models.

fal.ai only hosts ACE-Step v1; Replicate has the actual ACE-Step 1.5
release (fishaudio/ace-step-1.5), which is the reason this module exists.
Mirrors backend.integrations.fal_music's per-model function shape so
music_provider.py can dispatch to it the same way.

Input schema verified against the live API
(GET /v1/models/fishaudio/ace-step-1.5 -> latest_version.openapi_schema):
prompt (str, style/genre description), lyrics (str, default "[Instrumental]"
-- there's no separate instrumental boolean, that literal string IS how you
request an instrumental track), duration (number, seconds).

fishaudio/ace-step-1.5 isn't an "official" Replicate model, so the
owner/name shorthand 404s -- predictions need an explicit version id. We
resolve the latest version at call time rather than hardcoding a hash so
this doesn't silently pin to a stale version.
"""

from __future__ import annotations

import os
from typing import Optional

import replicate

from backend.integrations.music_types import Clip
from backend.secrets import REPLICATE_API_TOKEN

os.environ.setdefault("REPLICATE_API_TOKEN", REPLICATE_API_TOKEN)

MODEL_ID = "fishaudio/ace-step-1.5"
DEFAULT_DURATION_SECONDS = 30


def generate_ace_step_15(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """fishaudio/ace-step-1.5 on Replicate."""
    arguments = {
        "prompt": style or "",
        "lyrics": lyrics or "[Instrumental]",
        "duration": duration or DEFAULT_DURATION_SECONDS,
    }

    if on_status:
        on_status("IN_PROGRESS")

    version_id = replicate.models.get(MODEL_ID).latest_version.id
    output = replicate.run(f"{MODEL_ID}:{version_id}", input=arguments)
    # Some Replicate models return a single FileOutput, others a list of
    # them -- normalize to one.
    file_output = output[0] if isinstance(output, list) else output
    audio_url = file_output.url

    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "ace_step_15.wav")
    audio_bytes = file_output.read()
    with open(dest, "wb") as fh:
        fh.write(audio_bytes)

    if on_status:
        on_status("COMPLETED")

    return Clip(
        id="",
        status="complete",
        audio_url=audio_url,
        path=dest,
        raw={"output_url": audio_url},
    )


def generate_stable_audio_25(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    duration: Optional[float] = None,
    on_status=None,
) -> Clip:
    """stability-ai/stable-audio-2.5 on Replicate."""
    prompt = ""
    if style:
        prompt += f"Style: {style} "
    if lyrics:
        prompt += f"Lyrics: {lyrics}"

    arguments = {
        "prompt": prompt.strip() or "A beautiful instrumental",
        "duration": int(duration) if duration else DEFAULT_DURATION_SECONDS,
    }

    if on_status:
        on_status("IN_PROGRESS")

    try:
        output = replicate.run("stability-ai/stable-audio-2.5", input=arguments)
    except Exception as e:
        # Fallback if that fails for some reason
        model_id = "stability-ai/stable-audio-2.5"
        version_id = replicate.models.get(model_id).latest_version.id
        output = replicate.run(f"{model_id}:{version_id}", input=arguments)

    file_output = output[0] if isinstance(output, list) else output
    audio_url = file_output.url if hasattr(file_output, "url") else str(file_output)

    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "stable_audio_25.wav")
    
    # Check if we got a FileOutput object or just a URL string
    if hasattr(file_output, "read"):
        audio_bytes = file_output.read()
        with open(dest, "wb") as fh:
            fh.write(audio_bytes)
    else:
        import requests
        response = requests.get(audio_url)
        response.raise_for_status()
        with open(dest, "wb") as fh:
            fh.write(response.content)

    if on_status:
        on_status("COMPLETED")

    return Clip(
        id="",
        status="complete",
        audio_url=audio_url,
        path=dest,
        raw={"output_url": audio_url},
    )
