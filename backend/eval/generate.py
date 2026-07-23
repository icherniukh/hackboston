"""Generate eval clips via the production music_provider path and persist them."""

from __future__ import annotations

import os
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from backend.integrations.ffmpeg import get_duration
from backend.integrations.music_provider import generate_clip
from backend.integrations.openrouter import generate_song_prompt

from backend.eval.store import (
    append_jsonl,
    create_run_dir,
    load_fixture,
    save_clip_audio,
    save_clip_meta,
    utc_now,
    write_json,
)


def _select(items: list[dict], ids: Optional[list[str]], *, enabled_key: Optional[str] = None) -> list[dict]:
    if ids:
        by_id = {item["id"]: item for item in items}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise ValueError(f"Unknown fixture ids: {missing}")
        return [by_id[i] for i in ids]
    if enabled_key:
        return [item for item in items if item.get(enabled_key, True)]
    return list(items)


def _resolve_prompt(
    *,
    message: dict,
    style: dict,
    lyrics_mode: str,
    lyrics_model: Optional[str],
    force_style_prompt: bool,
) -> dict:
    """Return lyrics + style_prompt + provenance for one (message, style) cell."""
    genre = style.get("genre")
    pinned = style.get("style_prompt")

    if lyrics_mode == "fixed":
        if not message.get("fixed_lyrics"):
            raise ValueError(
                f"lyrics_mode=fixed requires fixed_lyrics on message {message['id']!r}"
            )
        style_prompt = pinned or message.get("fixed_style_prompt")
        style_source = "pinned" if pinned or message.get("fixed_style_prompt") else "pipeline"
        if not style_prompt:
            prompt = generate_song_prompt(
                input_message=message["input_message"],
                genre=genre,
                model=lyrics_model,
            )
            style_prompt = prompt["style_prompt"]
            style_source = "pipeline"
        return {
            "lyrics": message["fixed_lyrics"],
            "style_prompt": style_prompt,
            "lyrics_source": "fixed",
            "style_source": style_source,
            "genre": genre,
            "lyrics_model": lyrics_model,
        }

    prompt = generate_song_prompt(
        input_message=message["input_message"],
        genre=genre,
        model=lyrics_model,
    )
    style_prompt = prompt["style_prompt"]
    style_source = "pipeline"
    if force_style_prompt and pinned:
        style_prompt = pinned
        style_source = "pinned_override"

    return {
        "lyrics": prompt["lyrics"],
        "style_prompt": style_prompt,
        "lyrics_source": "pipeline",
        "style_source": style_source,
        "genre": genre,
        "lyrics_model": lyrics_model or "z-ai/glm-5.2",
    }


def _run_one(
    *,
    run_dir: str,
    message: dict,
    style: dict,
    model: dict,
    lyrics_mode: str,
    lyrics_model: Optional[str],
    force_style_prompt: bool,
    duration: float,
) -> dict:
    clip_id = str(uuid.uuid4())
    work_dir = os.path.join(run_dir, "clips", clip_id, "_work")
    os.makedirs(work_dir, exist_ok=True)

    meta: dict[str, Any] = {
        "clip_id": clip_id,
        "created_at": utc_now(),
        "message_id": message["id"],
        "input_message": message["input_message"],
        "style_id": style["id"],
        "style_label": style.get("label"),
        "music_model": model["id"],
        "music_model_label": model.get("label"),
        "lyrics_mode": lyrics_mode,
        "duration_requested": duration,
        "error": None,
        "audio_path": None,
        "duration_seconds": None,
        "lyrics": None,
        "style_prompt": None,
        "lyrics_source": None,
        "style_source": None,
        "genre": style.get("genre"),
        "lyrics_model": lyrics_model,
        "provider_raw": None,
    }

    try:
        prompt = _resolve_prompt(
            message=message,
            style=style,
            lyrics_mode=lyrics_mode,
            lyrics_model=lyrics_model,
            force_style_prompt=force_style_prompt,
        )
        meta.update({
            "lyrics": prompt["lyrics"],
            "style_prompt": prompt["style_prompt"],
            "lyrics_source": prompt["lyrics_source"],
            "style_source": prompt["style_source"],
            "genre": prompt.get("genre"),
            "lyrics_model": prompt.get("lyrics_model"),
        })

        clip = generate_clip(
            out_dir=work_dir,
            provider=model["id"],
            lyrics=prompt["lyrics"],
            style=prompt["style_prompt"],
            duration=duration,
        )
        rel_audio = save_clip_audio(run_dir=run_dir, clip_id=clip_id, src_path=clip.path)
        abs_audio = os.path.join(run_dir, rel_audio)
        meta["audio_path"] = rel_audio
        meta["duration_seconds"] = round(get_duration(abs_audio), 2)
        meta["provider_clip_id"] = clip.id
        meta["provider_audio_url"] = clip.audio_url
        # Keep raw small-ish; full fal payloads can be large.
        raw = clip.raw or {}
        meta["provider_raw"] = {k: raw[k] for k in list(raw)[:20]} if isinstance(raw, dict) else raw
    except Exception as e:
        meta["error"] = f"{type(e).__name__}: {e}"
        meta["traceback"] = traceback.format_exc()

    save_clip_meta(run_dir, clip_id, meta)
    append_jsonl(os.path.join(run_dir, "results.jsonl"), {
        "clip_id": clip_id,
        "message_id": meta["message_id"],
        "style_id": meta["style_id"],
        "music_model": meta["music_model"],
        "audio_path": meta["audio_path"],
        "error": meta["error"],
        "lyrics": meta["lyrics"],
        "style_prompt": meta["style_prompt"],
    })
    return meta


def generate_run(
    *,
    label: str = "eval",
    message_ids: Optional[list[str]] = None,
    style_ids: Optional[list[str]] = None,
    model_ids: Optional[list[str]] = None,
    lyrics_mode: str = "pipeline",
    lyrics_model: Optional[str] = None,
    force_style_prompt: bool = False,
    duration: float = 30.0,
    max_workers: int = 2,
) -> str:
    messages = _select(load_fixture("messages.json"), message_ids)
    styles = _select(load_fixture("styles.json"), style_ids)
    models = _select(load_fixture("models.json"), model_ids, enabled_key="enabled")
    if not models:
        raise ValueError("No models selected (check fixtures/models.json enabled flags or --models).")

    run_dir = create_run_dir(label)
    config = {
        "created_at": utc_now(),
        "label": label,
        "lyrics_mode": lyrics_mode,
        "lyrics_model": lyrics_model,
        "force_style_prompt": force_style_prompt,
        "duration": duration,
        "max_workers": max_workers,
        "messages": [m["id"] for m in messages],
        "styles": [s["id"] for s in styles],
        "models": [m["id"] for m in models],
        "n_jobs": len(messages) * len(styles) * len(models),
    }
    write_json(os.path.join(run_dir, "run.json"), config)

    jobs = [
        (message, style, model)
        for message in messages
        for style in styles
        for model in models
    ]

    print(f"Eval run: {run_dir}")
    print(f"Jobs: {len(jobs)} ({len(messages)} messages × {len(styles)} styles × {len(models)} models)")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(
                _run_one,
                run_dir=run_dir,
                message=message,
                style=style,
                model=model,
                lyrics_mode=lyrics_mode,
                lyrics_model=lyrics_model,
                force_style_prompt=force_style_prompt,
                duration=duration,
            )
            for message, style, model in jobs
        ]
        for fut in as_completed(futures):
            meta = fut.result()
            status = "ERROR" if meta.get("error") else "ok"
            print(
                f"  [{status}] {meta['music_model']} | {meta['message_id']} | {meta['style_id']}"
                + (f" — {meta['error']}" if meta.get("error") else f" → {meta['audio_path']}")
            )

    return run_dir
