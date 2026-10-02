"""Bluesky author feeds via the free public AppView — the usable half of "scan Twitter".

X has had no free read API since 2023 and its terms forbid scraping a timeline, so this
reads Bluesky instead, where `app.bsky.feed.getAuthorFeed` needs no key, no account and
no rate-limit deal. Checked on 2026-10-02: author feeds answer 200 unauthenticated;
`app.bsky.feed.searchPosts` answers 403 unless you are logged in, so keyword search
across the whole network is deliberately not supported here. Name the accounts instead
— for first-hand announcements that is the better instrument anyway.

What makes a post worth reading is usually the link card attached to it, so the card's
title and description are what the model reads, with the post's own text as the lede.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from ..models import Paper

AUTHOR_FEED = (
    "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
    "?actor={actor}&limit={limit}&filter={filter}"
)
FILTERS = ("posts_no_replies", "posts_with_replies", "posts_with_media", "posts_and_author_threads")
MAX_LIMIT = 100
TEXT_CHARS = 1200
TITLE_CHARS = 140


def fetch_bluesky(
    source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path
) -> list[Paper]:
    if source.get("query") or source.get("queries"):
        raise ValueError(
            "bluesky keyword search needs a logged-in session (searchPosts answers 403 "
            "unauthenticated), which Paper Radar does not do. List accounts in `actors` instead."
        )
    actors = source.get("actors") or ([source["actor"]] if source.get("actor") else [])
    if not actors and not source.get("file"):
        raise ValueError("bluesky source needs `actors = [\"handle.bsky.social\", ...]`")
    limit = min(int(source.get("limit", 50)), MAX_LIMIT)
    post_filter = str(source.get("filter", "posts_no_replies"))
    if post_filter not in FILTERS:
        raise ValueError(f"bluesky filter must be one of {', '.join(FILTERS)}, not {post_filter!r}")

    if source.get("file"):
        pages = [json.loads((base_dir / source["file"]).read_text(encoding="utf-8"))]
    else:
        pages = [
            json.loads(
                getter(
                    AUTHOR_FEED.format(
                        actor=urllib.parse.quote(str(actor)), limit=limit, filter=post_filter
                    )
                )
            )
            for actor in actors
        ]

    papers: list[Paper] = []
    for page in pages:
        papers.extend(
            parse_bluesky(
                page,
                min_likes=int(source.get("min_likes", 0)),
                min_reposts=int(source.get("min_reposts", 0)),
                require_link=bool(source.get("require_link", False)),
                include_reposts=bool(source.get("include_reposts", False)),
                langs=[str(x) for x in (source.get("langs") or [])],
            )
        )
    return papers


def _rkey(uri: str) -> str:
    return uri.rsplit("/", 1)[-1] if uri else ""


def _external(post: dict[str, Any]) -> dict[str, str]:
    """The link card, from the hydrated view. Absent on a text-only or image post."""
    embed = post.get("embed") or {}
    external = embed.get("external")
    if isinstance(external, dict):
        return {k: str(external.get(k) or "") for k in ("uri", "title", "description")}
    return {}


def parse_bluesky(
    page: dict[str, Any],
    *,
    min_likes: int = 0,
    min_reposts: int = 0,
    require_link: bool = False,
    include_reposts: bool = False,
    langs: list[str] | None = None,
) -> list[Paper]:
    papers: list[Paper] = []
    for item in page.get("feed") or []:
        # A repost is someone else's post arriving through this feed. Skipping them is
        # the default: they are the same item twice, and the radar dedupes by id anyway.
        if item.get("reason") and not include_reposts:
            continue
        post = item.get("post") or {}
        record = post.get("record") or {}
        if langs and not (set(record.get("langs") or []) & set(langs)):
            continue
        if int(post.get("likeCount") or 0) < min_likes or int(post.get("repostCount") or 0) < min_reposts:
            continue
        card = _external(post)
        if require_link and not card.get("uri"):
            continue
        author = post.get("author") or {}
        handle = str(author.get("handle") or "")
        uri = str(post.get("uri") or "")
        permalink = f"https://bsky.app/profile/{handle}/post/{_rkey(uri)}" if handle else ""
        text = " ".join(str(record.get("text") or "").split())
        categories = [f"@{handle}"] if handle else []
        if card.get("uri"):
            host = urllib.parse.urlsplit(card["uri"]).hostname or ""
            if host:
                categories.append(host.removeprefix("www."))
        papers.append(
            Paper(
                # The rkey is unique per author, not globally, so the whole at:// URI is
                # what gets hashed.
                id=f"bsky:{hashlib.sha1(uri.encode()).hexdigest()[:16]}",
                source="bluesky",
                title=card.get("title") or _clip(text, TITLE_CHARS) or "(no text)",
                abstract=_abstract(text, card),
                url=card.get("uri") or permalink,
                authors=[str(author.get("displayName") or handle)] if author else [],
                categories=categories,
                published=str(record.get("createdAt") or post.get("indexedAt") or ""),
                discussion=permalink,
                metrics={
                    "likes": int(post.get("likeCount") or 0),
                    "reposts": int(post.get("repostCount") or 0),
                    "replies": int(post.get("replyCount") or 0),
                },
            )
        )
    return papers


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _abstract(text: str, card: dict[str, str]) -> str:
    parts = [text[:TEXT_CHARS]]
    if card.get("description"):
        parts.append(f"Linked page: {card['description']}")
    return " ".join(p for p in parts if p).strip()
