# Music-model eval harness
#
# Generate clips (production music_provider path), store every audio file with
# prompt/model metadata, then score lyrics + style with a multimodal LLM judge.
#
# Quick start (from repo root, venv active):
#
#   python -m backend.eval list
#   python -m backend.eval run --messages museum,codex-tokens --styles none,indie-pop --models minimax-v2.6,replicate-ace-step-1.5
#   python -m backend.eval judge <run_dir>
#   python -m backend.eval run --messages museum --styles tech-house --models suno --judge
#
# Edit fixtures before big runs:
#   fixtures/messages.json  — input texts (add fixed_lyrics for lyrics-mode=fixed)
#   fixtures/styles.json    — genre / pinned style_prompt (yours to rewrite)
#   fixtures/models.json    — music_provider keys; enabled=false hides from default runs
#
# Each run lives under runs/<name>/:
#   run.json          — matrix config
#   results.jsonl     — one line per clip (quick index)
#   summary.json      — per-model average judge scores
#   clips/<uuid>/
#     audio.*         — generated clip
#     meta.json       — model, prompts, message, style, duration, errors
#     judge.json      — LLM scores + heard_lyrics + rationale
