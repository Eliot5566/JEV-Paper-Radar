"""Hugging Face Daily Papers — what the community upvoted, via huggingface.co/api/daily_papers.

Checked against the live API on 2026-10-23: each date returns a JSON array of up to 50
items (`limit` raises it), each `{paper: {id, title, summary, upvotes, authors, ...},
numComments, ...}`. The id is a bare arXiv id with no version, so a paper that also
arrives through the arXiv source dedupes against it instead of being judged twice.
Weekends return `[]`, not an error.

Two properties decide what this source is good for.

The list lags arXiv. A day's list held papers first posted 2 to 15 days earlier, which
is inside the default 14-day dedupe window: a paper your arXiv source already judged is
skipped here, not shown again with its upvotes. So the value is papers trending OUTSIDE
your arXiv categories — the cs.CV paper everyone is talking about, on a radar that reads
cs.CL — plus the upvote count on the occasional paper that arrives the same day.

And the list for today fills up during the day. A run at 02:00 UTC sees part of it, and
a Monday run sees an empty Saturday and Sunday, so `days` (default 4) reaches back far
enough to read Friday's list in full. Items already seen are deduped before judging, so
reaching back costs a request per day and nothing else.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from ..ids import normalize_paper_id
from ..models import Paper

API_URL = "https://huggingface.co/api/daily_papers?date={day}&limit={limit}"
MAX_LIMIT = 100


def fetch_huggingface(
    source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path, today: date
) -> list[Paper]:
    min_upvotes = int(source.get("min_upvotes", 0))
    if source.get("file"):
        pages = [json.loads((base_dir / source["file"]).read_text(encoding="utf-8"))]
    else:
        days = max(1, int(source.get("days", 4)))
        limit = min(int(source.get("limit", MAX_LIMIT)), MAX_LIMIT)
        pages = []
        for back in range(days):
            day = (today - timedelta(days=back)).isoformat()
            payload = getter(API_URL.format(day=day, limit=limit))
            if not payload.strip():
                raise ValueError(f"huggingface returned an empty response for {day}")
            pages.append(json.loads(payload))
    # The same paper can sit on two days' lists; keep the first, which is the newest day.
    seen: dict[str, Paper] = {}
    for page in pages:
        for paper in parse_daily_papers(page, min_upvotes=min_upvotes):
            seen.setdefault(paper.id, paper)
    return list(seen.values())


def parse_daily_papers(page: Any, *, min_upvotes: int = 0) -> list[Paper]:
    if not isinstance(page, list):
        raise ValueError("huggingface daily_papers did not return a list")
    papers: list[Paper] = []
    for item in page:
        if not isinstance(item, dict):
            continue
        paper = item.get("paper") or {}
        raw_id = str(paper.get("id") or "").strip()
        if not raw_id:
            continue
        upvotes = int(paper.get("upvotes") or 0)
        if upvotes < min_upvotes:
            continue
        pid = normalize_paper_id(raw_id)
        if not pid.startswith("arxiv:"):
            pid = f"hf:{raw_id}"
        papers.append(
            Paper(
                id=pid,
                source="huggingface",
                title=" ".join(str(paper.get("title") or item.get("title") or "").split()),
                abstract=" ".join(str(paper.get("summary") or item.get("summary") or "").split()),
                url=f"https://arxiv.org/abs/{raw_id}",
                authors=[
                    str(a.get("name"))
                    for a in paper.get("authors") or []
                    if isinstance(a, dict) and a.get("name") and not a.get("hidden")
                ],
                published=str(paper.get("publishedAt") or ""),
                discussion=f"https://huggingface.co/papers/{raw_id}",
                metrics={"upvotes": upvotes, "comments": int(item.get("numComments") or 0)},
            )
        )
    return papers
