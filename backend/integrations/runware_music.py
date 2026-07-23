"""Thin client for Runware API music/audio generation."""

from __future__ import annotations

import os
import asyncio
import uuid
import requests
from typing import Optional

from backend.integrations.music_types import Clip
from backend.secrets import RUNWARE_API_KEY

os.environ.setdefault("RUNWARE_API_KEY", RUNWARE_API_KEY)

DEFAULT_MODEL = "suno/suno-v3" # Replace with your target Runware model


def build_audio_inference_request(*, task_id: str, model: str, lyrics: Optional[str], style: Optional[str]) -> dict:
    """Build the exact request shape supported by this Runware adapter."""
    prompt = ""
    if style:
        prompt += f"Style: {style}\n"
    if lyrics:
        prompt += f"Lyrics: {lyrics}"
    return {
        "taskType": "audioInference",
        "taskUUID": task_id,
        "model": model,
        "positivePrompt": prompt,
    }


def generate_runware(
    *,
    out_dir: str,
    lyrics: Optional[str] = None,
    style: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    on_status=None,
) -> Clip:
    """Runware audio generation."""

    if on_status:
        on_status("IN_PROGRESS")

    async def _generate():
        from runware import Runware
        api_key = os.environ.get("RUNWARE_API_KEY")
        if not api_key:
            raise ValueError("RUNWARE_API_KEY is not set.")
            
        async with Runware(api_key=api_key, transport="rest") as client:
            request = build_audio_inference_request(
                task_id=str(uuid.uuid4()), model=model, lyrics=lyrics, style=style
            )
            return await client.run(request)
            
    # Run the async generation block in a synchronous context
    results = asyncio.run(_generate())
    
    if not results:
        raise RuntimeError("No results returned from Runware API.")
    
    # Runware typically returns a list of results for requests
    result = results[0] if isinstance(results, list) else results
    
    # Try to extract the URL from the response
    if "audioURL" in result:
        audio_url = result["audioURL"]
    elif "url" in result:
        audio_url = result["url"]
    else:
        # Fallback if the shape is unexpected
        raise RuntimeError(f"Could not find audio URL in Runware response: {result}")

    # Download the audio file
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "runware_audio.wav")
    
    response = requests.get(audio_url)
    response.raise_for_status()
    with open(dest, "wb") as f:
        f.write(response.content)

    if on_status:
        on_status("COMPLETED")

    return Clip(
        id="",
        status="complete",
        audio_url=audio_url,
        path=dest,
        raw={"output_url": audio_url, "model": model, "response": result},
    )
