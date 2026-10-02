"""Subreddit listings via Reddit's public JSON API.

Two things make a subreddit different from an arXiv listing, and both show up here.

A Reddit post is often a bare link: the title is all the text there is. So the domain
goes into `categories`, where the model can see it — "links to openai.com" is most of
what separates an announcement from coverage of an announcement.

And a brand-new post has a score of 1 whether it is a leak from a frontier lab or a
screenshot of a chatbot being rude. `listing = "top"` with `t = "day"` asks the
subreddit who was right, which is what you want from a once-a-day run. `min_score` and
`min_comments` are the floors under that.

Access, as of 2026-10: since 2025-11-11 (Reddit's "Responsible Builder Policy") the
self-serve app form at reddit.com/prefs/apps no longer creates apps — new API access
goes through a Data Access Request that Reddit answers by email, reportedly in 2–4
weeks and not always favourably. Since 2026-05-30 unauthenticated `.json` requests
return 403 to everyone. So this source works only with credentials Reddit has already
approved: set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET and it uses the OAuth host.

Without them, a subreddit's public RSS (`/r/<sub>/top/.rss?t=day`) is a plain Atom feed
and can be read with the ordinary `rss` source — no scores or comment counts, but the
`top` ranking is still Reddit's. See radars/signal.toml.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
from pathlib import Path
from typing import Any, Callable

from ..http import http_get, post_json
from ..models import Paper

PUBLIC = "https://www.reddit.com/r/{sub}/{listing}.json?limit={limit}&raw_json=1{extra}"
OAUTH = "https://oauth.reddit.com/r/{sub}/{listing}?limit={limit}&raw_json=1{extra}"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
LISTINGS = ("top", "hot", "new", "rising")
PERIODS = ("hour", "day", "week", "month", "year", "all")
MAX_LIMIT = 100
ABSTRACT_CHARS = 2000


def _token() -> str | None:
    """A client-credentials token, when the app is registered. None otherwise."""
    client_id, secret = os.environ.get("REDDIT_CLIENT_ID", ""), os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not (client_id and secret):
        return None
    basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    payload = post_json(
        TOKEN_URL,
        {"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        form=True,
    )
    return (payload or {}).get("access_token")


def fetch_reddit(
    source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path
) -> list[Paper]:
    subs = source.get("subreddits") or ([source["subreddit"]] if source.get("subreddit") else [])
    listing = str(source.get("listing", "top"))
    period = str(source.get("period", "day"))
    limit = min(int(source.get("limit", MAX_LIMIT)), MAX_LIMIT)
    if listing not in LISTINGS:
        raise ValueError(f"reddit listing must be one of {', '.join(LISTINGS)}, not {listing!r}")
    if period not in PERIODS:
        raise ValueError(f"reddit period must be one of {', '.join(PERIODS)}, not {period!r}")

    if source.get("file"):
        pages = [json.loads((base_dir / source["file"]).read_text(encoding="utf-8"))]
    else:
        token = _token()
        extra = f"&t={period}" if listing == "top" else ""
        template, fetch = (OAUTH, _authed(token)) if token else (PUBLIC, getter)
        pages = []
        for sub in subs:
            url = template.format(sub=sub, listing=listing, limit=limit, extra=extra)
            try:
                pages.append(json.loads(fetch(url)))
            except urllib.error.HTTPError as error:
                if error.code in (403, 429) and not token:
                    raise ValueError(
                        f"reddit returned {error.code} for r/{sub}. Unauthenticated JSON has been "
                        "closed since 2026-05-30 and new API access needs Reddit's approval. Set "
                        "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET if you have approved "
                        "credentials, or read the subreddit's /top/.rss feed with the rss source."
                    ) from error
                raise

    papers: list[Paper] = []
    for page in pages:
        papers.extend(
            parse_listing(
                page,
                min_score=int(source.get("min_score", 0)),
                min_comments=int(source.get("min_comments", 0)),
                allow_nsfw=bool(source.get("allow_nsfw", False)),
                require_link=bool(source.get("require_link", False)),
            )
        )
    return papers


def _authed(token: str | None) -> Callable[[str], str]:
    def fetch(url: str) -> str:
        return http_get(url, headers={"Authorization": f"Bearer {token}"})

    return fetch


def parse_listing(
    page: dict[str, Any],
    *,
    min_score: int = 0,
    min_comments: int = 0,
    allow_nsfw: bool = False,
    require_link: bool = False,
) -> list[Paper]:
    papers: list[Paper] = []
    for child in (page.get("data") or {}).get("children") or []:
        if child.get("kind") != "t3":  # t3 is a post; comments and other kinds are not
            continue
        post = child.get("data") or {}
        if post.get("stickied") or (post.get("over_18") and not allow_nsfw):
            continue
        if int(post.get("score") or 0) < min_score or int(post.get("num_comments") or 0) < min_comments:
            continue
        is_self = bool(post.get("is_self"))
        if require_link and is_self:
            continue
        sub = post.get("subreddit") or "reddit"
        permalink = post.get("permalink") or ""
        discussion = f"https://www.reddit.com{permalink}" if permalink else ""
        link = (post.get("url_overridden_by_dest") or post.get("url") or "").strip()
        # A self post's `url` is its own permalink, so there is nothing else to point at.
        target = discussion if is_self else (link or discussion)
        domain = (post.get("domain") or "").removeprefix("self.")
        categories = [f"r/{sub}"]
        if not is_self and domain:
            categories.append(domain)
        if post.get("link_flair_text"):
            categories.append(str(post["link_flair_text"]))
        papers.append(
            Paper(
                id=f"reddit:{post.get('id')}",
                source=f"r/{sub}",
                title=" ".join(str(post.get("title") or "").split()),
                abstract=_abstract(post, is_self=is_self, domain=domain),
                url=target,
                authors=[str(post["author"])] if post.get("author") else [],
                categories=categories,
                published=str(post.get("created_utc") or ""),
                discussion=discussion,
                metrics={
                    "points": int(post.get("score") or 0),
                    "comments": int(post.get("num_comments") or 0),
                },
            )
        )
    return papers


def _abstract(post: dict[str, Any], *, is_self: bool, domain: str) -> str:
    """What the model reads. For a link post the title is usually all there is, so the
    destination is spelled out in words rather than left in a URL the model cannot
    reliably parse."""
    body = " ".join(str(post.get("selftext") or "").split())[:ABSTRACT_CHARS]
    if is_self or not domain:
        return body
    where = f"Posted as a link to {domain}."
    return f"{where} {body}".strip()
