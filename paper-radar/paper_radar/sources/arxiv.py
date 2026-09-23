"""arXiv daily announcements via the official RSS feeds (rss.arxiv.org).

One request per run covers every requested category. Items carry an
`arxiv:announce_type` of new / cross / replace / replace-cross; by default we keep
new submissions and cross-lists and skip revisions of older papers.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

from ..models import Paper

RSS_URL = "https://rss.arxiv.org/rss/{categories}"
NS = {"arxiv": "http://arxiv.org/schemas/atom", "dc": "http://purl.org/dc/elements/1.1/"}

# Every top-level archive; `categories = ["*"]` means "all of arXiv".
ALL_ARCHIVES = [
    "astro-ph", "cond-mat", "cs", "econ", "eess", "gr-qc", "hep-ex", "hep-lat", "hep-ph", "hep-th",
    "math", "math-ph", "nlin", "nucl-ex", "nucl-th", "physics", "q-bio", "q-fin", "quant-ph", "stat",
]

_ID_RE = re.compile(r"arXiv:(\S+?)(?:v\d+)?\s")
_ABS_RE = re.compile(r"/abs/([^\s?#]+?)(?:v\d+)?$")


def feed_url(categories: list[str]) -> str:
    cats = ALL_ARCHIVES if "*" in categories else categories
    return RSS_URL.format(categories="+".join(cats))


def fetch_arxiv(source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path) -> list[Paper]:
    if source.get("file"):
        text = (base_dir / source["file"]).read_text(encoding="utf-8")
    else:
        text = getter(feed_url(list(source.get("categories", ["cs.AI"]))))
    return parse_arxiv_rss(
        text,
        include_cross=bool(source.get("include_cross_lists", True)),
        include_replacements=bool(source.get("include_replacements", False)),
    )


def _authors(raw: str) -> list[str]:
    raw = raw.replace(" and ", ", ")
    return [name.strip() for name in raw.split(",") if name.strip()]


def parse_arxiv_rss(text: str, *, include_cross: bool = True, include_replacements: bool = False) -> list[Paper]:
    root = ET.fromstring(text)
    papers: list[Paper] = []
    for item in root.iter("item"):
        announce = (item.findtext("arxiv:announce_type", default="", namespaces=NS) or "").strip()
        if announce.startswith("replace") and not include_replacements:
            continue
        if announce == "cross" and not include_cross:
            continue
        description = item.findtext("description", default="") or ""
        link = (item.findtext("link", default="") or "").strip()
        match = _ID_RE.search(description + " ") or _ABS_RE.search(link)
        if not match:
            continue
        arxiv_id = match.group(1)
        abstract = description.split("Abstract:", 1)[1] if "Abstract:" in description else description
        title = " ".join((item.findtext("title", default="") or "").split())
        papers.append(
            Paper(
                id=f"arxiv:{arxiv_id}",
                source="arxiv",
                title=title,
                abstract=" ".join(abstract.split()),
                url=link or f"https://arxiv.org/abs/{arxiv_id}",
                authors=_authors(item.findtext("dc:creator", default="", namespaces=NS) or ""),
                categories=[c.text.strip() for c in item.findall("category") if c.text],
                published=(item.findtext("pubDate", default="") or "").strip(),
                announce_type=announce,
            )
        )
    return papers
