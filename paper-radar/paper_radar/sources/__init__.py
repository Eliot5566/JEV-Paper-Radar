"""Paper sources. Each returns a list of `Paper`; `collect` dedupes across sources."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable

from ..http import http_get
from ..models import Paper
from .arxiv import fetch_arxiv
from .biorxiv import fetch_biorxiv
from .rss import fetch_rss

Getter = Callable[[str], str]


def collect(
    sources: list[dict[str, Any]],
    *,
    today: date,
    base_dir: Path,
    getter: Getter = http_get,
    log: Callable[[str], None] = print,
) -> list[Paper]:
    papers: dict[str, Paper] = {}
    for source in sources:
        kind = source["type"]
        try:
            if kind == "arxiv":
                batch = fetch_arxiv(source, getter=getter, base_dir=base_dir)
            elif kind in ("biorxiv", "medrxiv"):
                batch = fetch_biorxiv(source, getter=getter, base_dir=base_dir, today=today)
            else:
                batch = fetch_rss(source, getter=getter, base_dir=base_dir)
        except Exception as error:  # one broken source must not kill the daily run
            log(f"  ! source {source.get('name') or kind} failed: {error}")
            continue
        added = 0
        for paper in batch:
            if paper.id not in papers:
                papers[paper.id] = paper
                added += 1
        log(f"  - {source.get('name') or kind}: {len(batch)} items ({added} new after dedupe)")
    return list(papers.values())
