"""Dispatches music generation to a configured provider.

Both backend.integrations.suno and backend.integrations.fal_music expose a
generate_clip(*, out_dir, lyrics, style, ...) -> Clip function; this module
picks between them so call sites don't need to know which provider is active.

Provider is chosen (in order): the `provider` kwarg, the MUSIC_PROVIDER env
var, then DEFAULT_PROVIDER.
"""

from __future__ import annotations

import os
from typing import Optional

from backend.integrations import fal_music, suno
from backend.integrations.music_types import Clip

DEFAULT_PROVIDER = "suno"

_PROVIDERS = {
    "suno": suno.generate_clip,
    "fal": fal_music.generate_clip,
}


def generate_clip(*, out_dir: str, provider: Optional[str] = None, **kwargs) -> Clip:
    provider = provider or os.environ.get("MUSIC_PROVIDER", DEFAULT_PROVIDER)
    try:
        fn = _PROVIDERS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown MUSIC_PROVIDER {provider!r}; choose from {sorted(_PROVIDERS)}."
        )
    return fn(out_dir=out_dir, **kwargs)
