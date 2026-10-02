"""Fold near-duplicate items into one story, before anything is judged.

A paper feed has no duplicates worth speaking of. A news feed is mostly duplicates: one
announcement, then fifteen outlets reporting the announcement, then three subreddits
linking the outlets. Judging all nineteen costs nineteen times as much and produces a
page that looks like a search-results listing.

So this runs before Jev, not after, and it is deliberately boring: exact match on a
canonicalised URL, plus token overlap on titles. No model, no embeddings, no cost. It is
better at being predictable than at being clever, which is the right trade for something
that silently drops items — every fold is kept on the survivor and shown on the page.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Callable, Iterable

from .models import Paper

# Dropped from titles before comparing. Short function words only: anything with meaning
# stays, because "OpenAI raises" and "OpenAI releases" must not collapse into each other.
STOPWORDS = frozenset(
    """a an the and or but if then than that this these those of in on at to for from by with
    as is are was were be been being has have had do does did will would can could may might
    its it their his her your our my out up new now how why what when who vs via""".split()
)
TRACKING_PREFIX = ("utm_", "mc_", "pk_")
TRACKING = frozenset(
    {"fbclid", "gclid", "igshid", "ref", "ref_src", "referrer", "source", "spm", "cmpid", "s"}
)
_WORD_RE = re.compile(r"[a-z0-9]+")
MIN_TOKENS = 3


def canonical_url(url: str) -> str:
    """Strip the parts of a URL that differ without the page differing."""
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    for prefix in ("www.", "m.", "amp."):
        host = host.removeprefix(prefix)
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING and not k.lower().startswith(TRACKING_PREFIX)
    ]
    path = re.sub(r"/(amp|amp\.html)$", "", parts.path.rstrip("/"))
    return urllib.parse.urlunsplit(("", host, path, urllib.parse.urlencode(sorted(query)), ""))


def tokens(title: str) -> frozenset[str]:
    return frozenset(w for w in _WORD_RE.findall(title.lower()) if w not in STOPWORDS and len(w) > 1)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _rank(paper: Paper) -> tuple[int, int, int]:
    """Which copy of a story to keep: the most discussed, then the most substantial."""
    return (sum(paper.metrics.values()), len(paper.abstract), -len(paper.title))


def fold(
    papers: list[Paper], *, threshold: float = 0.6, rank: Callable[[Paper], tuple] = _rank
) -> list[Paper]:
    """Return one Paper per story, each carrying the others it absorbed in `duplicates`.

    Input order is preserved for the survivors, so a run stays reproducible.
    """
    groups: list[list[Paper]] = []
    by_url: dict[str, int] = {}
    # token -> groups containing it, so only plausible pairs are ever compared. A naive
    # all-pairs pass is O(n²) and a busy day is a few thousand items.
    by_token: dict[str, list[int]] = {}

    for paper in papers:
        key = canonical_url(paper.url)
        index = by_url.get(key) if key else None
        if index is None:
            index = _match(paper, groups, by_token, threshold)
        if index is None:
            index = len(groups)
            groups.append([])
            for token in tokens(paper.title):
                by_token.setdefault(token, []).append(index)
        groups[index].append(paper)
        if key and key not in by_url:
            by_url[key] = index

    survivors: list[Paper] = []
    for group in groups:
        best = max(group, key=rank)
        others = [p for p in group if p is not best]
        if others:
            best.duplicates = [
                *best.duplicates,
                *({"title": p.title, "url": p.url or p.discussion, "source": p.source} for p in others),
            ]
        survivors.append(best)
    return survivors


def _match(
    paper: Paper, groups: list[list[Paper]], by_token: dict[str, list[int]], threshold: float
) -> int | None:
    mine = tokens(paper.title)
    if len(mine) < MIN_TOKENS:
        # Too short to compare safely: "GPT-5 is out" and "GPT-5 is here" are one story,
        # but so are a hundred pairs that are not. Short titles stand alone.
        return None
    candidates = {index for token in mine for index in by_token.get(token, ())}
    best_score, best_index = 0.0, None
    for index in candidates:
        for other in groups[index]:
            score = jaccard(mine, tokens(other.title))
            if score > best_score:
                best_score, best_index = score, index
    return best_index if best_score >= threshold else None
