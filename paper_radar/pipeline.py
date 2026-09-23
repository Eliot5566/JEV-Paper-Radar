"""The daily run: collect -> dedupe -> judge every paper with Jev -> decide -> store -> render -> notify."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from .config import Config
from .jev import Backend, JevError
from .models import Paper
from .notify import send_all
from .questions import build_questions
from .render import day_stats, render_archive, render_day, render_feed
from .scoring import Decision, decide
from .sources import Getter, collect
from .store import Store
from .summarize import summarize_top

Log = Callable[[str], None]


@dataclass
class RunResult:
    day: str
    fetched: int
    judged: int
    failed: int
    decisions: list[Decision]
    seconds: float
    tokens: int
    cost: float

    def counts(self) -> dict[str, int]:
        return {b: sum(1 for d in self.decisions if d.band == b) for b in ("must_read", "maybe", "skip", "excluded")}


def estimate_tokens_per_paper(config: Config, avg_paper_chars: int = 1600) -> int:
    """Rough estimate: fixed request overhead + questions + a typical title and abstract (~4 chars/token)."""
    questions = build_questions(config)
    return 250 + len(json.dumps(questions)) // 4 + avg_paper_chars // 4


def judge_all(
    backend: Backend,
    papers: list[Paper],
    questions: dict[str, dict[str, Any]],
    config: Config,
    log: Log = print,
) -> tuple[list[Decision], list[tuple[Paper, str]]]:
    decisions: list[Decision] = []
    failures: list[tuple[Paper, str]] = []
    fatal: list[JevError] = []
    stop = threading.Event()
    lock = threading.Lock()

    def work(paper: Paper) -> Decision | None:
        if stop.is_set():
            return None
        try:
            result = backend.decide(paper.state(), questions)
        except JevError as error:
            if error.fatal:
                stop.set()
                with lock:
                    fatal.append(error)
            with lock:
                failures.append((paper, str(error)))
            return None
        return decide(paper, result, config)

    done = 0
    with ThreadPoolExecutor(max_workers=config.jev.concurrency) as pool:
        futures = [pool.submit(work, p) for p in papers]
        for future in as_completed(futures):
            decision = future.result()
            done += 1
            if decision is not None:
                decisions.append(decision)
            if done % 250 == 0:
                log(f"  … {done}/{len(papers)} judged")
    if fatal:
        raise fatal[0]
    return decisions, failures


def _record_run(store: Store, result: RunResult, backend: Backend) -> None:
    """One line per run in data/runs.jsonl, including days with nothing new."""
    store.append_run(
        {
            "day": result.day,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "backend": backend.name,
            "model": result.decisions[0].model if result.decisions else backend.model,
            "fetched": result.fetched,
            "judged": result.judged,
            "failed": result.failed,
            **result.counts(),
            "input_tokens": result.tokens,
            "cost_usd": round(result.cost, 6),
            "seconds": round(result.seconds, 1),
        }
    )


def rebuild_site(config: Config, store: Store, *, mock: bool = False) -> list[str]:
    """Regenerate every page from the audit trail (cheap, so the site is never stale)."""
    site = config.site_path
    site.mkdir(parents=True, exist_ok=True)
    (site / ".nojekyll").write_text("", encoding="utf-8")
    runs = store.load_runs()
    days = store.days()
    rows: list[tuple[str, dict[str, Any]]] = []
    feed_items: list[tuple[str, Decision]] = []
    for day in days:
        decisions = store.load_decisions(day)
        stats = day_stats(day, decisions, runs)
        rows.append((day, stats))
        day_mock = mock or stats.get("backend") == "mock"
        (site / f"{day}.html").write_text(render_day(config, day, decisions, stats, mock=day_mock), encoding="utf-8")
    for day in days[-config.output.feed_days :]:
        shown = [d for d in store.load_decisions(day) if d.band in ("must_read", "maybe")]
        feed_items.extend((day, d) for d in sorted(shown, key=lambda d: d.relevance, reverse=True))
    feed_items.sort(key=lambda item: item[0], reverse=True)
    if days:
        latest = days[-1]
        (site / "index.html").write_text((site / f"{latest}.html").read_text(encoding="utf-8"), encoding="utf-8")
    else:
        empty_stats = {"judged": 0, "must_read": 0, "maybe": 0, "excluded": 0, "tokens": 0, "cost": 0.0, "seconds": 0}
        (site / "index.html").write_text(render_day(config, "No runs yet", [], empty_stats, mock=mock), encoding="utf-8")
    (site / "archive.html").write_text(render_archive(config, rows), encoding="utf-8")
    (site / "feed.xml").write_text(render_feed(config, feed_items), encoding="utf-8")
    return days


def run(
    config: Config,
    backend: Backend,
    *,
    today: date,
    getter: Getter | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    notify: bool = True,
    env: dict[str, str] | None = None,
    log: Log = print,
) -> RunResult:
    day = today.isoformat()
    store = Store(config.data_path)
    started = time.monotonic()

    log(f"Collecting papers for {day}")
    kwargs: dict[str, Any] = {"today": today, "base_dir": config.base_dir, "log": log}
    if getter is not None:
        kwargs["getter"] = getter
    papers = collect(config.sources, **kwargs)
    fetched = len(papers)
    seen = store.seen_ids(today, config.output.dedupe_days)
    fresh = [p for p in papers if p.id not in seen and p.title]
    cap = min(config.max_papers, limit) if limit else config.max_papers
    if len(fresh) > cap:
        log(f"  ! {len(fresh)} new papers exceeds the cap of {cap}; judging the first {cap}")
        fresh = fresh[:cap]
    questions = build_questions(config)
    per_paper = estimate_tokens_per_paper(config)
    log(
        f"{fetched} fetched, {len(fresh)} new. {len(questions)} questions per paper "
        f"(≈{per_paper} tokens, ≈${len(fresh) * per_paper * config.jev.price_per_mtok / 1e6:.4f} estimated)"
    )
    if dry_run or not fresh:
        quiet = RunResult(day, fetched, 0, 0, [], time.monotonic() - started, 0, 0.0)
        if not dry_run:
            # Still record the run and rebuild: data/ must exist for the workflow's commit
            # step, and the Pages artifact has to stay valid on days with nothing new.
            _record_run(store, quiet, backend)
            rebuild_site(config, store)
        return quiet

    log(f"Asking {backend.name} ({backend.model}) about {len(fresh)} papers")
    decisions, failures = judge_all(backend, fresh, questions, config, log=log)
    for paper, reason in failures[:5]:
        log(f"  ! {paper.id}: {reason}")
    if failures:
        log(f"  ! {len(failures)} paper(s) failed and will be retried next run")

    summarize_top(config.summaries, decisions, env=env, log=log)
    store.write_decisions(day, decisions)
    seconds = time.monotonic() - started
    tokens = sum(d.input_tokens for d in decisions)
    cost = sum(d.cost for d in decisions)
    result = RunResult(day, fetched, len(decisions), len(failures), decisions, seconds, tokens, cost)
    _record_run(store, result, backend)
    rebuild_site(config, store)
    if notify:
        sent = send_all(config, day, decisions, env=env, log=log)
        if sent:
            log(f"Sent digest via {', '.join(sent)}")
    c = result.counts()
    log(
        f"Done: {len(decisions):,} read → {c['maybe'] + c['must_read']} shortlisted → {c['must_read']} must-read "
        f"({c['excluded']} excluded) in {seconds:.0f}s, {tokens:,} tokens, ≈${cost:.4f}"
    )
    return result
