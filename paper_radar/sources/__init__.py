"""Paper sources. Each returns a list of `Paper`; `collect` dedupes across sources."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable

from ..http import http_get
from ..models import Paper
from .arxiv import fetch_arxiv
from .biorxiv import fetch_biorxiv
from .pubmed import fetch_pubmed
from .rss import fetch_rss

Getter = Callable[[str], str]


def collect(
    sources: list[dict[str, Any]],
    *,
    today: date,
    base_dir: Path,
    getter: Getter = http_get,
    log: Callable[[str], None] = print,
    failures: list[dict[str, str]] | None = None,
) -> list[Paper]:
    """Fetch every source, skipping the ones that break.

    A source that is down is invisible otherwise: the page still renders, it just says
    "1 read" and looks like the filter went wrong. Pass `failures` and the caller can
    record what was missing so the page can say so.
    """
    papers: dict[str, Paper] = {}
    for source in sources:
        kind = source["type"]
        try:
            if kind == "arxiv":
                batch = fetch_arxiv(source, getter=getter, base_dir=base_dir)
            elif kind in ("biorxiv", "medrxiv"):
                batch = fetch_biorxiv(source, getter=getter, base_dir=base_dir, today=today)
            elif kind == "pubmed":
                batch = fetch_pubmed(source, getter=getter, base_dir=base_dir)
            else:
                batch = fetch_rss(source, getter=getter, base_dir=base_dir)
        except Exception as error:  # one broken source must not kill the daily run
            name = source.get("name") or kind
            log(f"  ! source {name} failed: {error}")
            if failures is not None:
                failures.append({"source": str(name), "error": str(error)[:300]})
            continue
        added = 0
        for paper in batch:
            if paper.id not in papers:
                papers[paper.id] = paper
                added += 1
        log(f"  - {source.get('name') or kind}: {len(batch)} items ({added} new after dedupe)")
    return list(papers.values())
