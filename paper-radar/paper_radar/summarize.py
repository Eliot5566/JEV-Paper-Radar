"""Optional System 2 step: one-sentence TL;DRs for the top-k papers only (the cascade pattern).

Jev decides what deserves attention across thousands of papers; a generative model writes a
sentence for the handful that made the cut, in the reader's language. Any OpenAI-compatible
`/chat/completions` endpoint works.
"""

from __future__ import annotations

import os
from typing import Callable

from .config import Summaries
from .http import post_json
from .scoring import Decision, rank

SYSTEM = (
    "You write a single-sentence TL;DR of a research paper for a busy researcher. "
    "Write in {language}. State the concrete contribution and the key result if the abstract gives one. "
    "No hype, no preamble, at most 45 words."
)


def summarize_top(
    settings: Summaries,
    decisions: list[Decision],
    *,
    env: dict[str, str] | None = None,
    poster: Callable[..., object] = post_json,
    log: Callable[[str], None] = print,
) -> int:
    if not settings.enabled:
        return 0
    env = dict(os.environ if env is None else env)
    key = env.get(settings.api_key_env, "")
    if not key or not settings.model:
        log(f"  ! summaries enabled but {settings.api_key_env} or summaries.model is missing; skipping")
        return 0
    chosen = [d for d in rank(decisions) if d.band in ("must_read", "maybe")][: settings.top_k]
    url = settings.base_url.rstrip("/") + "/chat/completions"
    done = 0
    for d in chosen:
        payload = {
            "model": settings.model,
            "max_tokens": 160,
            "messages": [
                {"role": "system", "content": SYSTEM.format(language=settings.language)},
                {"role": "user", "content": f"Title: {d.paper.title}\n\nAbstract: {d.paper.abstract}"},
            ],
        }
        try:
            data = poster(url, payload, headers={"Authorization": f"Bearer {key}"}, timeout=60)
            d.summary = str(data["choices"][0]["message"]["content"]).strip()  # type: ignore[index]
            done += 1
        except Exception as error:
            log(f"  ! summary failed for {d.paper.id}: {error}")
    return done
