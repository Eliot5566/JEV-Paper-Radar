"""Paper id normalisation, shared by the CLI and the feedback harvester."""

from __future__ import annotations

import re

ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}$|^[a-z\-]+(\.[A-Z]{2})?/\d{7}$")
# A PMID is 7-9 digits with no dot, so it can never collide with an arXiv id.
PMID = re.compile(r"^\d{7,9}$")
PUBMED_URL = re.compile(r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d{7,9})/?$")


def normalize_paper_id(raw: str) -> str:
    """Accept `2609.01234`, `2609.01234v2`, an arXiv or PubMed URL, a bare PMID,
    or an already-prefixed id."""
    value = raw.strip()
    pubmed = PUBMED_URL.match(value)
    if pubmed:
        return f"pubmed:{pubmed.group(1)}"
    value = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", value).removesuffix(".pdf")
    stripped = re.sub(r"v\d+$", "", value)
    if ARXIV_ID.match(stripped):
        return f"arxiv:{stripped}"
    if PMID.match(stripped):
        return f"pubmed:{stripped}"
    return value
