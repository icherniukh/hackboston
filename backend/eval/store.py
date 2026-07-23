"""Persist eval runs: audio files + per-clip metadata + aggregate indexes."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Optional

EVAL_ROOT = os.path.dirname(__file__)
RUNS_DIR = os.path.join(EVAL_ROOT, "runs")
FIXTURES_DIR = os.path.join(EVAL_ROOT, "fixtures")
COUNTER_PATH = os.path.join(RUNS_DIR, ".run_counter")


def load_fixture(name: str) -> Any:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path) as f:
        return json.load(f)


def _next_seq() -> int:
    os.makedirs(RUNS_DIR, exist_ok=True)
    current = 0
    if os.path.exists(COUNTER_PATH):
        with open(COUNTER_PATH) as f:
            current = int(f.read().strip() or 0)
    nxt = current + 1
    with open(COUNTER_PATH, "w") as f:
        f.write(str(nxt))
    return nxt


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if not slug:
        raise ValueError(f"label {label!r} has no usable characters")
    return slug


def create_run_dir(label: str = "eval") -> str:
    os.makedirs(RUNS_DIR, exist_ok=True)
    now = datetime.now()
    name = (
        f"{now.strftime('%b%d').lower()}-{_slugify(label)}-"
        f"{now.strftime('%I%M%p').lower()}-{_next_seq():03d}"
    )
    path = os.path.join(RUNS_DIR, name)
    os.makedirs(path, exist_ok=False)
    os.makedirs(os.path.join(path, "clips"), exist_ok=True)
    return path


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def append_jsonl(path: str, row: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def clip_dir(run_dir: str, clip_id: str) -> str:
    path = os.path.join(run_dir, "clips", clip_id)
    os.makedirs(path, exist_ok=True)
    return path


def save_clip_audio(*, run_dir: str, clip_id: str, src_path: str) -> str:
    """Copy generated audio into the run tree; return relative path from run_dir."""
    dest_dir = clip_dir(run_dir, clip_id)
    ext = os.path.splitext(src_path)[1] or ".bin"
    dest_name = f"audio{ext}"
    dest_abs = os.path.join(dest_dir, dest_name)
    shutil.copy2(src_path, dest_abs)
    return os.path.relpath(dest_abs, run_dir)


def save_clip_meta(run_dir: str, clip_id: str, meta: dict) -> str:
    path = os.path.join(clip_dir(run_dir, clip_id), "meta.json")
    write_json(path, meta)
    return path


def save_judge(run_dir: str, clip_id: str, judgment: dict) -> str:
    path = os.path.join(clip_dir(run_dir, clip_id), "judge.json")
    write_json(path, judgment)
    return path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_clip_metas(run_dir: str) -> list[dict]:
    clips_root = os.path.join(run_dir, "clips")
    if not os.path.isdir(clips_root):
        return []
    metas: list[dict] = []
    for name in sorted(os.listdir(clips_root)):
        meta_path = os.path.join(clips_root, name, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                metas.append(json.load(f))
    return metas


def resolve_run_dir(path_or_name: str) -> str:
    if os.path.isabs(path_or_name) and os.path.isdir(path_or_name):
        return path_or_name
    candidate = os.path.join(RUNS_DIR, path_or_name)
    if os.path.isdir(candidate):
        return candidate
    if os.path.isdir(path_or_name):
        return os.path.abspath(path_or_name)
    raise FileNotFoundError(f"No eval run at {path_or_name!r}")


def write_scores_csv(run_dir: str, metas: list[dict] | None = None) -> str:
    import csv

    metas = metas if metas is not None else list_clip_metas(run_dir)
    path = os.path.join(run_dir, "scores.csv")
    fields = [
        "clip_id", "music_model", "message_id", "style_id", "error",
        "lyrics_fidelity", "style_adherence", "style_bleed", "hook_fit", "overall",
        "heard_lyrics", "style_notes", "rationale", "audio_path",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for meta in metas:
            judgment = {}
            judge_path = os.path.join(run_dir, "clips", meta["clip_id"], "judge.json")
            if os.path.isfile(judge_path):
                with open(judge_path) as jf:
                    judgment = json.load(jf)
            scores = judgment.get("scores") or {}
            writer.writerow({
                "clip_id": meta["clip_id"],
                "music_model": meta.get("music_model"),
                "message_id": meta.get("message_id"),
                "style_id": meta.get("style_id"),
                "error": meta.get("error") or judgment.get("error"),
                "lyrics_fidelity": scores.get("lyrics_fidelity"),
                "style_adherence": scores.get("style_adherence"),
                "style_bleed": scores.get("style_bleed"),
                "hook_fit": scores.get("hook_fit"),
                "overall": scores.get("overall"),
                "heard_lyrics": judgment.get("heard_lyrics"),
                "style_notes": judgment.get("style_notes"),
                "rationale": judgment.get("rationale"),
                "audio_path": meta.get("audio_path"),
            })
    return path


def build_summary(run_dir: str) -> dict:
    metas = list_clip_metas(run_dir)
    by_model: dict[str, list[dict]] = {}
    for meta in metas:
        model = meta.get("music_model") or "unknown"
        judgment = None
        judge_path = os.path.join(run_dir, "clips", meta["clip_id"], "judge.json")
        if os.path.isfile(judge_path):
            with open(judge_path) as f:
                judgment = json.load(f)
        entry = {"clip_id": meta["clip_id"], "ok": meta.get("error") is None, "judgment": judgment}
        by_model.setdefault(model, []).append(entry)

    model_stats = {}
    for model, entries in by_model.items():
        judged = [e["judgment"] for e in entries if e.get("judgment") and "scores" in e["judgment"] and e["judgment"]["scores"]]
        def avg(key: str) -> Optional[float]:
            vals = [j["scores"][key] for j in judged if key in j.get("scores", {})]
            return round(sum(vals) / len(vals), 3) if vals else None

        model_stats[model] = {
            "n": len(entries),
            "errors": sum(1 for e in entries if not e["ok"]),
            "judged": len(judged),
            "avg_lyrics_fidelity": avg("lyrics_fidelity"),
            "avg_style_adherence": avg("style_adherence"),
            "avg_style_bleed": avg("style_bleed"),
            "avg_hook_fit": avg("hook_fit"),
            "avg_overall": avg("overall"),
        }

    summary = {
        "run_dir": run_dir,
        "n_clips": len(metas),
        "models": model_stats,
        "updated_at": utc_now(),
        "scores_csv": os.path.relpath(write_scores_csv(run_dir, metas), run_dir),
    }
    write_json(os.path.join(run_dir, "summary.json"), summary)
    return summary
