# fal.ai as an alternative music provider

## Context

Music generation currently goes exclusively through Suno (`backend/integrations/suno.py`). The goal is provider redundancy/cost flexibility: add fal.ai's ACE-Step model as a second, swappable provider, selected by config rather than hardcoded.

Out of scope (tracked separately as `falai-5mp`): moving demucs/whisper to fal.ai. That's a VPS-portability concern, not a redundancy concern — `demucs-mlx` only runs on Apple Silicon, so it'll need a hosted replacement whenever this moves off the current laptop, but that's independent of this work.

Not in scope: image generation / lyrics generation alternatives, per-request client override (the design leaves room for it but doesn't implement it), automatic failover between providers (manual toggle only).

## Architecture

Two sibling provider modules with a matching `generate_clip(...) -> Clip` return shape, plus a thin dispatcher that `app.py` calls instead of importing a provider directly.

## Components

- **`backend/integrations/music_types.py`** (new) — the `Clip` dataclass (`id`, `path`, `audio_url`, `title`, `raw`), extracted from `suno.py` so both providers return the same shape. `path` becomes a real declared field (currently set dynamically post-construction in `suno.py`).

- **`backend/integrations/suno.py`** — unchanged except importing `Clip` from `music_types` instead of defining it locally.

- **`backend/integrations/fal_music.py`** (new) — wraps `fal-ai/ace-step` via the `fal_client` package.
  - `DEFAULT_DURATION_SECONDS = 30` — caps generation length/cost; ACE-Step is billed per second generated, and the pipeline trims audio after generation anyway (based on detected vocal silence bounds), so there's no benefit to letting it run longer.
  - `generate_clip(*, out_dir, lyrics=None, style=None, duration=None, on_status=None) -> Clip`: `style` → ACE-Step's `tags` input, `lyrics` → `lyrics` input, `duration` defaults to `DEFAULT_DURATION_SECONDS`. Downloads the returned WAV into `out_dir`.
  - Mirrors `suno.py`'s CLI entrypoint (`python -m backend.integrations.fal_music --lyrics ... --style ...`) for standalone testing before wiring into the full pipeline.
  - Exact ACE-Step input/output field names to be confirmed against the live schema at `https://fal.ai/models/fal-ai/ace-step/api` during implementation — current understanding is based on doc summarization, not a verified schema dump.

- **`backend/integrations/music_provider.py`** (new) — dispatcher: `generate_clip(*, out_dir, lyrics=None, style=None, provider=None, **kwargs)`. Picks `provider` if passed, else `os.environ["MUSIC_PROVIDER"]`, else `"suno"`. This is the seam for a future client-supplied `provider` field — `app.py` would just need to pass `data.get("provider")` through; not implemented now.

- **`backend/app.py`** — one-line change: import `generate_clip` from `music_provider` instead of `suno`. No other changes; the existing call site only ever passes `lyrics`, `style`, `out_dir`, which both providers accept.

- **`backend/secrets.py.example`** — add `FAL_API_KEY=''`. `fal_client` reads auth from the `FAL_KEY` env var, so `fal_music.py` does `os.environ.setdefault("FAL_KEY", FAL_API_KEY)` on import to bridge the existing secrets pattern into what the SDK expects.

- **`backend/requirements.txt`** — add `fal-client`.

## Config

- `MUSIC_PROVIDER` env var: `"suno"` (default, unchanged behavior) or `"fal"`.
- `FAL_API_KEY` secret in `backend/secrets.py`.

## Data flow

Unchanged shape: `generate_song_endpoint` → `_produce_song` → `pool.submit(generate_clip, lyrics=, style=, out_dir=)` → dispatcher resolves provider → returns `Clip` → rest of the pipeline (demucs, trim, cover art, m4a assembly) only touches `clip.path`, so it doesn't care which provider produced it. `separate_vocals` already skips its MP3→WAV conversion step for non-`.mp3` input, so ACE-Step's WAV output flows straight into demucs-mlx with no extra glue.

## Error handling

`fal_client` raises its own exceptions on failure; these propagate through `ThreadPoolExecutor.result()` exactly like `SunoError` does today, surfacing as Flask's default 500. No new handling needed — consistent with current behavior.

## Testing

1. Standalone: run `fal_music.py`'s CLI directly with `FAL_API_KEY` set — verify the ACE-Step integration in isolation.
2. Set `MUSIC_PROVIDER=fal`, hit `/generate-song` (existing bruno request), confirm the full pipeline produces a playable `.m4a`.
3. Confirm `MUSIC_PROVIDER` unset still uses Suno — regression check.
