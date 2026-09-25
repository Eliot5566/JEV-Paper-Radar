"""bioRxiv / medRxiv via the public details API (api.biorxiv.org).

Only version-1 records are kept, so revisions of older preprints do not reappear.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from ..models import Paper

API_URL = "https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}"
MAX_PAGES = 100


def _norm(category: str) -> str:
    return category.strip().lower().replace(" ", "_")


def fetch_biorxiv(
    source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path, today: date
) -> list[Paper]:
    server = source.get("server") or source["type"]
    if server not in ("biorxiv", "medrxiv"):
        raise ValueError(f"unknown server {server!r}")
    wanted = {_norm(c) for c in source.get("categories", [])}
    pages: list[dict[str, Any]] = []
    if source.get("file"):
        pages.append(json.loads((base_dir / source["file"]).read_text(encoding="utf-8")))
    else:
        days = int(source.get("days", 1))
        start, end = today - timedelta(days=days), today
        cursor = 0
        for _ in range(MAX_PAGES):
            url = API_URL.format(server=server, start=start, end=end, cursor=cursor)
            payload = getter(url)
            if not payload.strip():
                # Observed 2026-09-26: the API answers 200 with content-type
                # application/json and an empty body, for every server and date range.
                # json.loads would report "Expecting value: line 1 column 1", which
                # sends you looking for a bug in the URL rather than at the service.
                raise ValueError(f"{server} returned an empty response for {start}..{end}; the API looks down")
            page = json.loads(payload)
            pages.append(page)
            collection = page.get("collection") or []
            messages = (page.get("messages") or [{}])[0]
            total = int(messages.get("total") or 0)
            cursor += len(collection)
            if not collection or cursor >= total:
                break
    return [p for page in pages for p in parse_biorxiv(page, server=server, wanted=wanted)]


def parse_biorxiv(page: dict[str, Any], *, server: str, wanted: set[str] | None = None) -> list[Paper]:
    papers: list[Paper] = []
    for record in page.get("collection") or []:
        if str(record.get("version", "1")) != "1":
            continue
        category = record.get("category", "")
        if wanted and _norm(category) not in wanted:
            continue
        doi = record.get("doi", "").strip()
        if not doi:
            continue
        papers.append(
            Paper(
                id=f"{server}:{doi}",
                source=server,
                title=" ".join(str(record.get("title", "")).split()),
                abstract=" ".join(str(record.get("abstract", "")).split()),
                url=f"https://www.{server}.org/content/{doi}v1",
                authors=[a.strip() for a in str(record.get("authors", "")).split(";") if a.strip()],
                categories=[category] if category else [],
                published=str(record.get("date", "")),
                announce_type="new",
            )
        )
    return papers
