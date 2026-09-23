"""Core data types shared across sources, the Jev client, scoring and rendering."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Paper:
    """One item from a source. `id` is globally unique, e.g. `arxiv:2609.01234`."""

    id: str
    source: str
    title: str
    abstract: str
    url: str
    authors: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    published: str = ""
    announce_type: str = ""

    def state(self) -> dict[str, Any]:
        """What Jev sees. Only the fields the questions need ("retrieve, then judge").

        Authors and affiliations are left out on purpose: they are irrelevant to topical
        relevance and irrelevant context lowers accuracy (Jev 1.13 jaggedness note #5).
        """
        state: dict[str, Any] = {"title": self.title, "abstract": self.abstract}
        if self.categories:
            state["categories"] = self.categories
        return state

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Paper":
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        known.setdefault("abstract", "")
        return cls(**known)


@dataclass
class JevResult:
    """A validated System One response for one paper."""

    answers: dict[str, dict[str, Any]]
    model: str
    input_tokens: int
    cost: float | None = None  # USD, when the backend reports it (OpenRouter does)
