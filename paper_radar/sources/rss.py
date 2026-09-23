"""Any RSS 2.0 or Atom feed: journals, lab blogs, Hacker News (hnrss.org), newsletters."""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

from ..models import Paper

ATOM = "{http://www.w3.org/2005/Atom}"
_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", text or "")).split())


def fetch_rss(source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path) -> list[Paper]:
    if source.get("file"):
        text = (base_dir / source["file"]).read_text(encoding="utf-8")
    else:
        text = getter(source["url"])
    return parse_feed(text, name=source.get("name") or "rss", limit=int(source.get("limit", 500)))


def _pid(name: str, key: str) -> str:
    return f"rss:{hashlib.sha1(f'{name}|{key}'.encode()).hexdigest()[:16]}"


def parse_feed(text: str, *, name: str, limit: int = 500) -> list[Paper]:
    root = ET.fromstring(text)
    papers: list[Paper] = []
    if root.tag == f"{ATOM}feed":
        for entry in root.findall(f"{ATOM}entry")[:limit]:
            link_el = entry.find(f"{ATOM}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{ATOM}link")
            link = link_el.get("href", "") if link_el is not None else ""
            key = entry.findtext(f"{ATOM}id") or link
            summary = entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content") or ""
            papers.append(
                Paper(
                    id=_pid(name, key),
                    source=name,
                    title=strip_html(entry.findtext(f"{ATOM}title") or ""),
                    abstract=strip_html(summary),
                    url=link,
                    authors=[a.findtext(f"{ATOM}name") or "" for a in entry.findall(f"{ATOM}author")],
                    published=entry.findtext(f"{ATOM}updated") or entry.findtext(f"{ATOM}published") or "",
                )
            )
        return papers
    for item in list(root.iter("item"))[:limit]:
        link = (item.findtext("link") or "").strip()
        key = item.findtext("guid") or link or item.findtext("title") or ""
        papers.append(
            Paper(
                id=_pid(name, key),
                source=name,
                title=strip_html(item.findtext("title") or ""),
                abstract=strip_html(item.findtext("description") or ""),
                url=link,
                authors=[a for a in [item.findtext("author") or item.findtext("{http://purl.org/dc/elements/1.1/}creator")] if a],
                categories=[c.text for c in item.findall("category") if c.text],
                published=item.findtext("pubDate") or "",
            )
        )
    return papers
