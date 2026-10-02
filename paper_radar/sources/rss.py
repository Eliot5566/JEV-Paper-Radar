"""Any RSS 2.0 or Atom feed: journals, lab blogs, Hacker News (hnrss.org), newsletters."""

from __future__ import annotations

import hashlib
import html
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

from ..models import Paper

ATOM = "{http://www.w3.org/2005/Atom}"
_TAG_RE = re.compile(r"<[^>]+>")
# Reddit's feeds link each entry to its comment thread and put the destination in the
# body as <a href="...">[link]</a>. The radar's convention is url = the thing itself,
# discussion = where people talk about it; without this, every Reddit card pointed at a
# thread, and URL-based folding could never match a Reddit post to the article it links.
_REDDIT_LINK_RE = re.compile(r'<a href="([^"]+)">\s*\[link\]\s*</a>')


def strip_html(text: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", text or "")).split())


def fetch_rss(source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path) -> list[Paper]:
    if source.get("file"):
        text = (base_dir / source["file"]).read_text(encoding="utf-8")
    else:
        if source.get("delay"):
            # For hosts that rate-limit anonymous readers per IP. Reddit's RSS answered 429
            # to every second request when four feeds were fetched back to back.
            time.sleep(float(source["delay"]))
        text = getter(source["url"])
    return parse_feed(text, name=source.get("name") or "rss", limit=int(source.get("limit", 500)))


def _pid(name: str, key: str) -> str:
    return f"rss:{hashlib.sha1(f'{name}|{key}'.encode()).hexdigest()[:16]}"


# A GitHub release feed titles every entry with just the tag — "v0.30.0", "b11335" —
# which is useless on a page and worse as the only thing the model gets to judge. The
# feed's own title says which project it is, so short entry titles borrow it.
TERSE_TITLE = re.compile(r"^(v?[\d][\w.\-]*|[a-z]{0,2}\d{3,})$", re.IGNORECASE)
TERSE_CHARS = 24
_FEED_TITLE_NOISE = re.compile(r"^(release notes from|releases? [-·|] |comments? on )", re.IGNORECASE)


def _feed_title(root: ET.Element) -> str:
    """The feed's own title, with the boilerplate GitHub puts in front of it removed."""
    raw = root.findtext(f"{ATOM}title") or root.findtext("./channel/title") or ""
    return _FEED_TITLE_NOISE.sub("", " ".join(raw.split())).strip()


def _title(entry_title: str, feed_title: str) -> str:
    entry_title = " ".join(entry_title.split())
    if not feed_title or not entry_title:
        return entry_title
    if len(entry_title) <= TERSE_CHARS and TERSE_TITLE.match(entry_title):
        return f"{feed_title} {entry_title}"
    return entry_title


def parse_feed(text: str, *, name: str, limit: int = 500) -> list[Paper]:
    root = ET.fromstring(text)
    feed_title = _feed_title(root)
    papers: list[Paper] = []
    if root.tag == f"{ATOM}feed":
        for entry in root.findall(f"{ATOM}entry")[:limit]:
            link_el = entry.find(f"{ATOM}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{ATOM}link")
            link = link_el.get("href", "") if link_el is not None else ""
            key = entry.findtext(f"{ATOM}id") or link
            summary = entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content") or ""
            discussion = ""
            target = _REDDIT_LINK_RE.search(html.unescape(summary))
            if target and "reddit.com" in link:
                destination = html.unescape(target.group(1))
                # A self post's [link] points back at its own thread; nothing to split.
                if destination.rstrip("/") != link.rstrip("/"):
                    discussion, link = link, destination
            papers.append(
                Paper(
                    id=_pid(name, key),
                    source=name,
                    title=_title(strip_html(entry.findtext(f"{ATOM}title") or ""), feed_title),
                    abstract=strip_html(summary),
                    url=link,
                    discussion=discussion,
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
                title=_title(strip_html(item.findtext("title") or ""), feed_title),
                abstract=strip_html(item.findtext("description") or ""),
                url=link,
                authors=[a for a in [item.findtext("author") or item.findtext("{http://purl.org/dc/elements/1.1/}creator")] if a],
                categories=[c.text for c in item.findall("category") if c.text],
                published=item.findtext("pubDate") or "",
            )
        )
    return papers
