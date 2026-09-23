"""Compose Jev's atomic answers into a decision. Code stays in control of the logic."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .models import JevResult, Paper
from .questions import CODE_KEY, EVIDENCE_KEY, EXCLUDE_PREFIX, INTEREST_PREFIX, PAPER_TYPE_KEY

BANDS = ("must_read", "maybe", "skip", "excluded")


@dataclass
class Decision:
    paper: Paper
    relevance: float
    band: str
    interests: dict[str, float]  # interest id -> P(statement is true)
    exclusions: dict[str, float]  # exclusion id -> P(statement is true)
    paper_type: str | None = None
    paper_type_confidence: float | None = None
    code: float | None = None
    evidence: float | None = None  # normalized to 0..1
    model: str = ""
    input_tokens: int = 0
    cost: float = 0.0
    summary: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def excluded_by(self) -> list[str]:
        return [k for k, v in self.exclusions.items() if v >= self.extra.get("exclude_threshold", 1.1)]

    def top_interests(self, n: int = 3, floor: float = 0.3) -> list[tuple[str, float]]:
        ranked = sorted(self.interests.items(), key=lambda kv: kv[1], reverse=True)
        return [(k, v) for k, v in ranked[:n] if v >= floor]

    def to_dict(self, *, full: bool = True) -> dict[str, Any]:
        paper = self.paper.to_dict()
        if not full:
            paper = {k: paper[k] for k in ("id", "source", "title", "url", "categories")}
        record = {
            "paper": paper,
            "relevance": round(self.relevance, 4),
            "band": self.band,
            "interests": {k: round(v, 4) for k, v in self.interests.items()},
            "exclusions": {k: round(v, 4) for k, v in self.exclusions.items()},
            "paper_type": self.paper_type,
            "paper_type_confidence": self.paper_type_confidence,
            "code": self.code,
            "evidence": self.evidence,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "cost": self.cost,
            "summary": self.summary,
            "extra": self.extra,
        }
        return record

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        return cls(
            paper=Paper.from_dict(data["paper"]),
            relevance=float(data["relevance"]),
            band=data["band"],
            interests=dict(data.get("interests") or {}),
            exclusions=dict(data.get("exclusions") or {}),
            paper_type=data.get("paper_type"),
            paper_type_confidence=data.get("paper_type_confidence"),
            code=data.get("code"),
            evidence=data.get("evidence"),
            model=data.get("model", ""),
            input_tokens=int(data.get("input_tokens") or 0),
            cost=float(data.get("cost") or 0.0),
            summary=data.get("summary"),
            extra=dict(data.get("extra") or {}),
        )


def combine(values: list[float], mode: str) -> float:
    if not values:
        return 0.0
    if mode == "noisy_or":
        return 1 - math.prod(1 - v for v in values)
    return max(values)


def decide(paper: Paper, result: JevResult, config: Config) -> Decision:
    answers = result.answers
    interests = {i.id: float(answers[INTEREST_PREFIX + i.id]["noul"]) for i in config.interests}
    exclusions = {e.id: float(answers[EXCLUDE_PREFIX + e.id]["noul"]) for e in config.exclusions}
    weighted = [interests[i.id] * i.weight for i in config.interests]
    relevance = combine(weighted, config.combine)

    t = config.thresholds
    if any(p >= t.exclude for p in exclusions.values()):
        band = "excluded"
    elif relevance >= t.must_read:
        band = "must_read"
    elif relevance >= t.maybe:
        band = "maybe"
    else:
        band = "skip"

    paper_type = confidence = code = evidence = None
    if PAPER_TYPE_KEY in answers:
        paper_type = answers[PAPER_TYPE_KEY]["choice"]
        confidence = float(answers[PAPER_TYPE_KEY].get("confidence", 0.0))
    if CODE_KEY in answers:
        code = float(answers[CODE_KEY]["noul"])
    if EVIDENCE_KEY in answers:
        levels = max(1, len(answers[EVIDENCE_KEY].get("legend") or {}) - 1)
        evidence = round(float(answers[EVIDENCE_KEY]["score"]) / levels, 4)

    cost = result.cost if result.cost is not None else result.input_tokens * config.jev.price_per_mtok / 1_000_000
    return Decision(
        paper=paper,
        relevance=relevance,
        band=band,
        interests=interests,
        exclusions=exclusions,
        paper_type=paper_type,
        paper_type_confidence=confidence,
        code=code,
        evidence=evidence,
        model=result.model,
        input_tokens=result.input_tokens,
        cost=cost,
        extra={"exclude_threshold": t.exclude},
    )


def rank(decisions: list[Decision]) -> list[Decision]:
    return sorted(decisions, key=lambda d: d.relevance, reverse=True)
