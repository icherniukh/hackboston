"""Dispatches music generation to a configured provider/model.

Every entry in _PROVIDERS exposes the same
generate_clip(*, out_dir, lyrics, style, ...) -> Clip shape; this module
picks between them so call sites don't need to know which one is active.
Adding a new model is just one new dict entry — no changes needed here
beyond that.

Provider is chosen (in order): the `provider` kwarg, the MUSIC_PROVIDER env
var, then DEFAULT_PROVIDER. "fal" is kept as an alias for "ace-step" (fal's
original default) so existing MUSIC_PROVIDER=fal setups keep working.
"""

from __future__ import annotations

import os
from typing import Optional

from backend.integrations import fal_music, replicate_music, suno
from backend.integrations.music_types import Clip

DEFAULT_PROVIDER = "suno"

_PROVIDERS = {
    "suno": suno.generate_clip,
    "fal": fal_music.generate_ace_step,  # back-compat alias
    "ace-step": fal_music.generate_ace_step,
    "ace-step-prompt": fal_music.generate_ace_step_prompt_to_audio,
    "minimax-v2": fal_music.generate_minimax_v2,
    "minimax-v2.5": fal_music.generate_minimax_v25,
    "minimax-v2.6": fal_music.generate_minimax_v26,
    "lyria3": fal_music.generate_lyria3,
    "elevenlabs": fal_music.generate_elevenlabs,
    "replicate-ace-step-1.5": replicate_music.generate_ace_step_15,
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
