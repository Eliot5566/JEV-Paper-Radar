"""Paper id normalisation, shared by the CLI and the feedback harvester."""

from __future__ import annotations

import re

ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}$|^[a-z\-]+(\.[A-Z]{2})?/\d{7}$")


def normalize_paper_id(raw: str) -> str:
    """Accept `2609.01234`, `2609.01234v2`, an arXiv URL, or an already-prefixed id."""
    value = raw.strip()
    value = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", value).removesuffix(".pdf")
    stripped = re.sub(r"v\d+$", "", value)
    if ARXIV_ID.match(stripped):
        return f"arxiv:{stripped}"
    return value
