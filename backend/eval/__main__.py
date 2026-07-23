"""CLI: python -m backend.eval …"""

from __future__ import annotations

import argparse
import json
import sys

from backend.eval.generate import generate_run
from backend.eval.judge import DEFAULT_JUDGE_MODEL, judge_run
from backend.eval.store import RUNS_DIR, build_summary, load_fixture, resolve_run_dir


def _csv_ids(value: str | None) -> list[str] | None:
    if not value or value.strip().lower() == "all":
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def cmd_list(_args: argparse.Namespace) -> int:
    for kind in ("messages", "styles", "models"):
        items = load_fixture(f"{kind}.json")
        print(f"\n{kind}:")
        for item in items:
            flag = ""
            if kind == "models":
                flag = " [enabled]" if item.get("enabled", True) else " [disabled]"
            print(f"  {item['id']:28} {item.get('label') or item.get('notes', '')}{flag}")
    print(f"\nruns dir: {RUNS_DIR}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    run_dir = generate_run(
        label=args.label,
        message_ids=_csv_ids(args.messages),
        style_ids=_csv_ids(args.styles),
        model_ids=_csv_ids(args.models),
        lyrics_mode=args.lyrics_mode,
        lyrics_model=args.lyrics_model,
        force_style_prompt=args.force_style_prompt,
        duration=args.duration,
        max_workers=args.workers,
    )
    if args.judge:
        summary = judge_run(run_dir, judge_model=args.judge_model, force=args.force_judge)
        print("\n=== summary ===")
        print(json.dumps(summary["models"], indent=2))
    else:
        print(f"\nGenerate done. Judge later with:\n  python -m backend.eval judge {run_dir}")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run)
    summary = judge_run(run_dir, judge_model=args.judge_model, force=args.force)
    print("\n=== summary ===")
    print(json.dumps(summary["models"], indent=2))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run)
    summary = build_summary(run_dir)
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.eval",
        description="Generate music-model eval clips, store audio+metadata, LLM-judge lyrics & style.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    list_p = sub.add_parser("list", help="Show fixture messages / styles / models")
    list_p.set_defaults(func=cmd_list)

    run_p = sub.add_parser("run", help="Generate clips for a message×style×model matrix")
    run_p.add_argument("--label", default="eval", help="Run directory label slug")
    run_p.add_argument("--messages", default="all", help="Comma-separated message ids, or 'all'")
    run_p.add_argument("--styles", default="all", help="Comma-separated style ids, or 'all'")
    run_p.add_argument(
        "--models",
        default=None,
        help="Comma-separated music_provider keys. Default: fixtures/models.json enabled=true",
    )
    run_p.add_argument(
        "--lyrics-mode",
        choices=("pipeline", "fixed"),
        default="pipeline",
        help="pipeline = generate_song_prompt; fixed = use message.fixed_lyrics when present",
    )
    run_p.add_argument("--lyrics-model", default=None, help="OpenRouter model for lyrics/style prompt")
    run_p.add_argument(
        "--force-style-prompt",
        action="store_true",
        help="After pipeline lyrics, replace style_prompt with fixtures/styles.json style_prompt when set",
    )
    run_p.add_argument("--duration", type=float, default=30.0)
    run_p.add_argument("--workers", type=int, default=2)
    run_p.add_argument("--judge", action="store_true", help="Run LLM judge after generation")
    run_p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    run_p.add_argument("--force-judge", action="store_true")
    run_p.set_defaults(func=cmd_run)

    judge_p = sub.add_parser("judge", help="LLM-judge an existing run (lyrics + style)")
    judge_p.add_argument("run", help="Run directory path or name under backend/eval/runs/")
    judge_p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    judge_p.add_argument("--force", action="store_true", help="Re-judge clips that already have judge.json")
    judge_p.set_defaults(func=cmd_judge)

    sum_p = sub.add_parser("summary", help="Rebuild summary.json from clip metas + judgments")
    sum_p.add_argument("run", help="Run directory path or name")
    sum_p.set_defaults(func=cmd_summary)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
