"""Command line: `paper-radar run | screen | demo | check | label | calibrate | harvest | rebuild | directory`."""

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
from .feedback import harvest
from .ids import normalize_paper_id
from .jev import JevError, MockBackend, make_backend
from .pipeline import estimate_tokens_per_paper, rebuild_site, run, run_screening
from .questions import build_questions, build_screening_questions
from .screening import format_performance, screening_performance
from .store import Store


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


def _load(path: str, base_dir: str | None = None):
    """Load a config, optionally re-basing its relative paths.

    `site_dir` and `data_dir` are resolved against the config file's own directory,
    which is what you want for `profiles/x.toml` sitting next to its data. It is not
    what you want for `radars/agents.toml` writing to "site/public/agents": that
    lands in radars/site/, which no one publishes. `--base-dir .` fixes it.
    """
    config = load_config(path)
    if base_dir:
        config.base_dir = Path(base_dir).resolve()
    return config


def _apply_env_defaults(config) -> None:
    """In GitHub Actions, a fork points its 👍/👎 links at its own repo with no config."""
    if not config.output.feedback_repo:
        config.output.feedback_repo = os.environ.get("GITHUB_REPOSITORY", "")


def cmd_run(args: argparse.Namespace) -> int:
    config = _load(args.config, args.base_dir)
    if getattr(args, "site_dir", None):
        # Publishing to a different folder than the config says is a deployment concern,
        # not a change to the radar: this repo keeps the shipped default (`site`) so a
        # fork's own page lands at its Pages root, and moves its own personal radar aside
        # so the root can be the public directory instead.
        config.output.site_dir = args.site_dir
    _apply_env_defaults(config)
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
    screening = config.screening.enabled
    questions = build_screening_questions(config) if screening else build_questions(config)
    per_paper = estimate_tokens_per_paper(config, questions=questions)
    if screening:
        print(
            f"Config OK (screening mode): {len(config.screening.include)} include criteria, "
            f"{len(config.screening.exclude)} exclude criteria, {len(config.sources)} sources"
        )
        print(f"Run it with: paper-radar screen -c {args.config}")
    else:
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
    pid = normalize_paper_id(args.paper_id)
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


def cmd_screen(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if not config.screening.enabled:
        print(
            "error: [screening] is not enabled in this config. A screening profile needs\n"
            "       enabled = true and at least one [[screening.include]] criterion.\n"
            "       See profiles/systematic-review.toml for a worked example.",
            file=sys.stderr,
        )
        return 2
    for warning in lint(config):
        print(f"warning: {warning}")

    store = Store(config.data_path)
    if args.report:
        report = screening_performance(
            store.eligibility_index(),
            store.load_labels(),
            target_recall=args.recall or config.screening.target_recall,
        )
        print(format_performance(report))
        return 0

    if args.backend:
        config.jev.backend = args.backend
    backend = make_backend(config.jev)
    result = run_screening(config, backend, today=_today(args.date), limit=args.limit)
    if result.screened == 0 and result.failed:
        return 1
    return 0


def cmd_directory(args: argparse.Namespace) -> int:
    """One page listing every public radar, so a visitor can subscribe without forking."""
    from .render import render_directory

    radars = []
    for path in args.configs:
        config = _load(path, args.base_dir)
        store = Store(config.data_path)
        days = store.days()
        entry = {
            "title": config.title,
            "tagline": config.output.tagline or "Every new paper, judged against plain-English interests.",
            "url": args.base.rstrip("/") + "/" + Path(config.output.site_dir).name + "/",
            "feed": args.base.rstrip("/") + "/" + Path(config.output.site_dir).name + "/feed.xml",
            "judged": None,
        }
        if days:
            day = days[-1]
            decisions = store.load_decisions(day)
            picks = sorted((d for d in decisions if d.band == "must_read"), key=lambda d: -d.relevance)
            runs = [r for r in store.load_runs() if r.get("day") == day]
            entry.update(
                day=day,
                # How many papers were read that day, not what the most recent run
                # judged: a rebuild that judges nothing would otherwise print
                # "0 read -> 28 worth opening", which reads as broken.
                judged=len(decisions),
                shortlisted=sum(1 for d in decisions if d.band in ("must_read", "maybe")),
                must_read=len(picks),
                cost=sum(float(r.get("cost_usd") or 0) for r in runs),
                top=[d.paper.title for d in picks[:3]],
                source_failures=sorted(
                    {str(f.get("source") or "?") for r in runs for f in (r.get("source_failures") or [])}
                ),
            )
        radars.append(entry)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_directory(radars), encoding="utf-8")
    live = sum(1 for r in radars if r["judged"])
    print(f"wrote {out} — {len(radars)} radars ({live} with a run recorded)")
    return 0


def cmd_harvest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    repo = args.repo or config.output.feedback_repo or os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        print('error: set output.feedback_repo = "owner/name" in radar.toml, or pass --repo', file=sys.stderr)
        return 2
    token = os.environ.get("GITHUB_TOKEN", "")
    result = harvest(repo, Store(config.data_path), token=token, close=not args.no_close and bool(token))
    print(f"Recorded {result.recorded} label(s) from issues, closed {result.closed}")
    if result.recorded and not token:
        print("note: set GITHUB_TOKEN to let the run close the issues it has already read")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    config = _load(args.config, args.base_dir)
    _apply_env_defaults(config)
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
    p.add_argument("--base-dir", help="resolve site_dir/data_dir against this directory instead of the config's own")
    p.add_argument("--site-dir", help="publish the page to this folder instead of output.site_dir")
    p.add_argument("--dry-run", action="store_true", help="fetch and estimate cost without calling Jev")
    p.add_argument("--no-notify", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("screen", help="title/abstract screening for a systematic review")
    p.add_argument("-c", "--config", default="review.toml")
    p.add_argument("--date", help="YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--limit", type=int, help="screen at most N records")
    p.add_argument("--backend", choices=["typesafe", "openrouter", "mock"], help="override jev.backend")
    p.add_argument("--report", action="store_true", help="measure recall and workload saved against your own decisions")
    p.add_argument("--recall", type=float, help="target recall for --report (default: screening.target_recall)")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("directory", help="build one page listing several radars, with each one's latest numbers")
    p.add_argument("configs", nargs="+", help="radar config files, in the order they should appear")
    p.add_argument("--out", required=True, help="where to write the page, e.g. site/public/index.html")
    p.add_argument("--base", default=".", help="path prefix the radar folders sit under, relative to --out")
    p.add_argument("--base-dir", help="resolve each config's site_dir/data_dir against this directory")
    p.set_defaults(func=cmd_directory)

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

    p = sub.add_parser("harvest", help="fold 👍/👎 issues into data/labels.jsonl and close them")
    p.add_argument("-c", "--config", default="radar.toml")
    p.add_argument("--repo", help='owner/name (defaults to output.feedback_repo)')
    p.add_argument("--no-close", action="store_true", help="leave the issues open")
    p.set_defaults(func=cmd_harvest)

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
