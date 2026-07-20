"""Resolve music providers and their provider-owned capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
import os
from typing import Any, Optional

from backend.integrations.music_types import Clip

DEFAULT_PROVIDER = "suno"


@dataclass(frozen=True)
class ProviderCapabilities:
    """Behavior guaranteed by one concrete provider integration."""

    supports_duration: bool = False
    supports_playback_url: bool = False


@dataclass(frozen=True)
class ProviderDefinition:
    """The provider boundary: adapter module, callable, and fixed model inputs."""

    module_name: str
    generate_name: str
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)
    fixed_kwargs: dict[str, Any] = field(default_factory=dict)


_PROVIDERS: dict[str, ProviderDefinition] = {
    "suno": ProviderDefinition(
        "backend.integrations.suno",
        "generate_clip",
        ProviderCapabilities(supports_playback_url=True),
    ),
    "fal": ProviderDefinition(
        "backend.integrations.fal_music",
        "generate_ace_step",
        ProviderCapabilities(supports_duration=True),
    ),
    "ace-step": ProviderDefinition(
        "backend.integrations.fal_music",
        "generate_ace_step",
        ProviderCapabilities(supports_duration=True),
    ),
    "ace-step-prompt": ProviderDefinition(
        "backend.integrations.fal_music",
        "generate_ace_step_prompt_to_audio",
        ProviderCapabilities(supports_duration=True),
    ),
    "minimax-v2": ProviderDefinition("backend.integrations.fal_music", "generate_minimax_v2"),
    "minimax-v2.5": ProviderDefinition("backend.integrations.fal_music", "generate_minimax_v25"),
    "minimax-v2.6": ProviderDefinition("backend.integrations.fal_music", "generate_minimax_v26"),
    "lyria3": ProviderDefinition("backend.integrations.fal_music", "generate_lyria3"),
    "elevenlabs": ProviderDefinition(
        "backend.integrations.fal_music",
        "generate_elevenlabs",
        ProviderCapabilities(supports_duration=True),
    ),
    "replicate-ace-step-1.5": ProviderDefinition(
        "backend.integrations.replicate_music",
        "generate_ace_step_15",
        ProviderCapabilities(supports_duration=True),
    ),
    "replicate-stable-audio-2.5": ProviderDefinition(
        "backend.integrations.replicate_music",
        "generate_stable_audio_25",
        ProviderCapabilities(supports_duration=True),
    ),
    "runware": ProviderDefinition("backend.integrations.runware_music", "generate_runware"),
    "runware:ace-step@v1.5-xl-sft": ProviderDefinition(
        "backend.integrations.runware_music",
        "generate_runware",
        fixed_kwargs={"model": "runware:ace-step@v1.5-xl-sft"},
    ),
    "runware:ace-step@v1.5-xl-turbo": ProviderDefinition(
        "backend.integrations.runware_music",
        "generate_runware",
        fixed_kwargs={"model": "runware:ace-step@v1.5-xl-turbo"},
    ),
    "runware:ace-step@v1.5-xl-base": ProviderDefinition(
        "backend.integrations.runware_music",
        "generate_runware",
        fixed_kwargs={"model": "runware:ace-step@v1.5-xl-base"},
    ),
}


def resolve_provider(provider: Optional[str] = None) -> tuple[str, ProviderDefinition]:
    """Return the selected provider's stable identifier and definition."""
    provider_id = provider or os.environ.get("MUSIC_PROVIDER", DEFAULT_PROVIDER)
    try:
        return provider_id, _PROVIDERS[provider_id]
    except KeyError as exc:
        raise ValueError(
            f"Unknown MUSIC_PROVIDER {provider_id!r}; choose from {sorted(_PROVIDERS)}."
        ) from exc


def provider_capabilities(provider: Optional[str] = None) -> ProviderCapabilities:
    """Expose capabilities without importing an adapter or validating its key."""
    _, definition = resolve_provider(provider)
    return definition.capabilities


def generate_clip(
    *,
    out_dir: str,
    provider: Optional[str] = None,
    duration: Optional[float] = None,
    **kwargs,
) -> Clip:
    """Generate a clip through one lazily loaded provider adapter."""
    _, definition = resolve_provider(provider)
    arguments = {**definition.fixed_kwargs, **kwargs}
    if duration is not None and definition.capabilities.supports_duration:
        arguments["duration"] = duration

    module = import_module(definition.module_name)
    generate = getattr(module, definition.generate_name)
    return generate(out_dir=out_dir, **arguments)


def mint_playback_url(provider: str, clip_id: str) -> str:
    """Mint provider-managed browser playback when that provider supports it."""
    _, definition = resolve_provider(provider)
    if not definition.capabilities.supports_playback_url:
        raise ValueError(f"Provider {provider!r} does not support source playback URLs.")

    module = import_module(definition.module_name)
    return module.mint_playback_url(clip_id)
