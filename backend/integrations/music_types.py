"""Shared result type for music-generation providers (Suno, fal.ai, ...)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Clip:
    """Result of a completed music generation, regardless of provider."""

    id: str
    status: str
    audio_url: str
    path: str = ""
    title: Optional[str] = None
    raw: dict = field(default_factory=dict)
