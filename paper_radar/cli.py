"""Command line: `paper-radar run | demo | check | label | calibrate | rebuild`."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from importlib import resources
from pathlib import Path

from . import __version__
from .calibrate import calibrate, format_report
from .config import ConfigError, lint, load_config
from .jev import JevError, MockBackend, make_backend
from .pipeline import estimate_tokens_per_paper, rebuild_site, run
from .questions import build_questions
from .store import Store

ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}$|^[a-z\-]+(\.[A-Z]{2})?/\d{7}$")


def _today(value: str | None) -> date:
    return date.fromisoformat(value) if value else datetime.now(timezone.utc).date()


def load_dotenv(path: Path) -> list[str]:
    """Read KEY=VALUE lines from a local .env into the environment, for local runs.

    Real environment variables always win, so GitHub Actions secrets are never shadowed.
    .env is git-ignored: keys belong there or in Actions secrets, never in a tracked file.
    """
    if not path.is_file():
        return []
    loaded: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def _normalize_id(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", raw).removesuffix(".pdf")
    raw = re.sub(r"v\d+$", "", raw) if ARXIV_ID.match(re.sub(r"v\d+$", "", raw)) else raw
    return f"arxiv:{raw}" if ARXIV_ID.match(raw) else raw


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    for warning in lint(config):
        print(f"warning: {warning}")
    if args.backend:
        config.jev.backend = args.backend
    backend = make_backend(config.jev)
    result = run(config, backend, today=_today(args.date), limit=args.limit, dry_run=args.dry_run, notify=not args.no_notify)
    if result.judged == 0 and result.failed:
        return 1
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    demo = resources.files("paper_radar") / "demo"
    for name in ("radar.demo.toml", "arxiv_demo.xml"):
        shutil.copyfile(str(demo / name), out / name)
    config = load_config(out / "radar.demo.toml")
    for day in (config.data_path / "decisions").glob("*"):
        day.unlink()
    if (config.data_path / "runs.jsonl").exists():
        (config.data_path / "runs.jsonl").unlink()
    run(config, MockBackend(), today=_today(args.date), notify=False)
    print(f"\nOpen {config.site_path / 'index.html'} in your browser.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    warnings = lint(config)
    questions = build_questions(config)
    per_paper = estimate_tokens_per_paper(config)
    print(f"Config OK: {len(config.interests)} interests, {len(config.exclusions)} exclusions, {len(config.sources)} sources")
    print(f"Backend: {config.jev.backend}  model: {config.jev.model or '(default)'}")
    print(f"Questions per paper: {len(questions)}  (≈{per_paper} input tokens per paper, rough estimate)")
    for n in (200, 1500, 5000):
        cost = n * per_paper * config.jev.price_per_mtok / 1e6
        print(f"  {n:>5} papers/day ≈ ${cost:.3f}/day ≈ ${cost * 22:.2f}/month (22 announcement days)")
    for warning in warnings:
        print(f"warning: {warning}")
    if args.show_questions:
        print(json.dumps(questions, indent=2, ensure_ascii=False))
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    store = Store(config.data_path)
    relevant = args.verdict.lower() in ("yes", "y", "1", "true", "relevant")
    pid = _normalize_id(args.paper_id)
    store.add_label(pid, relevant, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print(f"Labelled {pid} as {'relevant' if relevant else 'not relevant'}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    store = Store(config.data_path)
    report = calibrate(
        store.relevance_index(),
        store.load_labels(),
        target_precision=args.precision,
        target_recall=args.recall,
    )
    print(format_report(report, args.precision, args.recall))
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    days = rebuild_site(config, Store(config.data_path))
    print(f"Rebuilt {len(days)} day page(s) in {config.site_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-radar", description="Let Jev read every new paper; see only the ones that matter.")
    parser.add_argument("--version", action="version", version=f"paper-radar {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="fetch, judge, store, render and notify")
    p.add_argument("-c", "--config", default="radar.toml")
    p.add_argument("--date", help="YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--limit", type=int, help="judge at most N papers (for a first test)")
    p.add_argument("--backend", choices=["typesafe", "openrouter", "mock"], help="override jev.backend")
    p.add_argument("--dry-run", action="store_true", help="fetch and estimate cost without calling Jev")
    p.add_argument("--no-notify", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("demo", help="offline demo with sample papers and a mock model (no API key)")
    p.add_argument("--out", default="paper-radar-demo")
    p.add_argument("--date", help="YYYY-MM-DD")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("check", help="validate radar.toml, lint interests, estimate cost")
    p.add_argument("-c", "--config", default="radar.toml")
    p.add_argument("--show-questions", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("label", help="record whether a paper was relevant to you")
    p.add_argument("paper_id", help="e.g. 2609.01234, arxiv:2609.01234, or an arXiv URL")
    p.add_argument("verdict", help="yes | no")
    p.add_argument("-c", "--config", default="radar.toml")
    p.set_defaults(func=cmd_label)

    p = sub.add_parser("calibrate", help="measure calibration on your labels and suggest thresholds")
    p.add_argument("-c", "--config", default="radar.toml")
    p.add_argument("--precision", type=float, default=0.9, help="target precision for must_read")
    p.add_argument("--recall", type=float, default=0.9, help="target recall for maybe")
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("rebuild", help="regenerate the site from data/ without calling Jev")
    p.add_argument("-c", "--config", default="radar.toml")
    p.set_defaults(func=cmd_rebuild)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(Path(".env"))
    config_path = getattr(args, "config", None)
    if config_path:
        load_dotenv(Path(config_path).resolve().parent / ".env")
    try:
        return args.func(args)
    except (ConfigError, JevError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
