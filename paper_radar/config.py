"""Load and validate `radar.toml`.

Unknown keys are rejected so a typo never silently disables a setting.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^[a-z0-9_]{1,40}$")
NEGATION_RE = re.compile(r"\b(not|no|never|without|except|unless|excluding|neither|nor)\b|n't\b", re.IGNORECASE)
BACKENDS = {"typesafe", "openrouter", "mock"}
SOURCE_TYPES = {"arxiv", "biorxiv", "medrxiv", "pubmed", "rss"}
SOURCE_KEYS = {
    "arxiv": {"categories", "include_cross_lists", "include_replacements"},
    "biorxiv": {"server", "days", "categories"},
    "medrxiv": {"server", "days", "categories"},
    "pubmed": {"query", "days", "datetype", "email", "max_records", "exclude_types"},
    "rss": {"url", "limit"},
}
COMBINE_MODES = {"max", "noisy_or"}
SCREEN_COMBINE = {"geometric", "min"}


class ConfigError(ValueError):
    """Raised when radar.toml is invalid."""


@dataclass
class Interest:
    id: str
    text: str
    label: str = ""
    weight: float = 1.0
    true: str | None = None
    false: str | None = None

    @property
    def display(self) -> str:
        return self.label or self.id.replace("_", " ")


@dataclass
class Exclusion:
    id: str
    text: str
    label: str = ""

    @property
    def display(self) -> str:
        return self.label or self.id.replace("_", " ")


@dataclass
class Criterion:
    """One eligibility criterion in a systematic review, phrased as a statement."""

    id: str
    text: str
    label: str = ""

    @property
    def display(self) -> str:
        return self.label or self.id.replace("_", " ")


@dataclass
class Screening:
    """Title/abstract screening for a systematic review.

    Unlike the daily radar, criteria are a conjunction: a record is eligible only if
    *every* include criterion holds, and any single exclude criterion disqualifies it.
    Because of that, every criterion you add is another chance to veto a record — the
    opposite of interests, where adding one can only create another chance to match.
    `threshold` is deliberately permissive by default — in screening, a missed study
    costs far more than an extra abstract to read, so the default errs toward reading.
    """

    enabled: bool = False
    target_recall: float = 0.95
    combine: str = "geometric"   # "geometric" (all criteria) or "min" (weakest link)
    threshold: float = 0.40
    exclude_threshold: float = 0.90
    include: list[Criterion] = field(default_factory=list)
    exclude: list[Criterion] = field(default_factory=list)


@dataclass
class Thresholds:
    must_read: float = 0.80
    maybe: float = 0.50
    exclude: float = 0.80


@dataclass
class JevSettings:
    backend: str = "typesafe"
    model: str | None = None
    base_url: str | None = None
    concurrency: int = 8
    requests_per_minute: int = 1000
    timeout: float = 20.0
    max_retries: int = 4
    price_per_mtok: float = 0.042


@dataclass
class Signals:
    paper_type: bool = True
    code_release: bool = True
    evidence: bool = False


@dataclass
class Output:
    site_dir: str = "site"
    data_dir: str = "data"
    feed_days: int = 7
    site_url: str = ""
    near_misses: int = 15
    dedupe_days: int = 14
    feedback_repo: str = ""  # "owner/name": adds 👍/👎 links that open a pre-filled issue
    tagline: str = ""        # replaces the one-line subtitle under the date


@dataclass
class Summaries:
    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    model: str = ""
    language: str = "English"
    top_k: int = 10
    api_key_env: str = "LLM_API_KEY"


@dataclass
class Config:
    title: str = "Paper Radar"
    max_papers: int = 3000
    combine: str = "max"
    sources: list[dict[str, Any]] = field(default_factory=list)
    interests: list[Interest] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)
    thresholds: Thresholds = field(default_factory=Thresholds)
    jev: JevSettings = field(default_factory=JevSettings)
    signals: Signals = field(default_factory=Signals)
    output: Output = field(default_factory=Output)
    summaries: Summaries = field(default_factory=Summaries)
    screening: Screening = field(default_factory=Screening)
    base_dir: Path = field(default_factory=lambda: Path("."))

    @property
    def site_path(self) -> Path:
        return self.base_dir / self.output.site_dir

    @property
    def data_path(self) -> Path:
        return self.base_dir / self.output.data_dir

    def resolve(self, path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else self.base_dir / candidate


def _build(cls: type, table: Any, where: str) -> Any:
    if table is None:
        return cls()
    if not isinstance(table, dict):
        raise ConfigError(f"[{where}] must be a table")
    allowed = {f.name for f in fields(cls)}
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"Unknown key(s) in [{where}]: {', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}")
    return cls(**table)


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("rb") as handle:
        try:
            raw = tomllib.load(handle)
        except tomllib.TOMLDecodeError as error:
            raise ConfigError(f"{path}: {error}") from error
    return parse_config(raw, base_dir=path.resolve().parent)


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> Config:
    top_allowed = {
        "radar", "jev", "thresholds", "signals", "output", "summaries",
        "sources", "interests", "exclude", "screening",
    }
    unknown = sorted(set(raw) - top_allowed)
    if unknown:
        raise ConfigError(f"Unknown top-level section(s): {', '.join(unknown)}")

    radar = raw.get("radar", {})
    radar_allowed = {"title", "max_papers", "combine"}
    bad = sorted(set(radar) - radar_allowed)
    if bad:
        raise ConfigError(f"Unknown key(s) in [radar]: {', '.join(bad)}")

    config = Config(
        title=radar.get("title", "Paper Radar"),
        max_papers=int(radar.get("max_papers", 3000)),
        combine=radar.get("combine", "max"),
        sources=list(raw.get("sources", [])),
        interests=[_build(Interest, item, "interests") for item in raw.get("interests", [])],
        exclusions=[_build(Exclusion, item, "exclude") for item in raw.get("exclude", [])],
        thresholds=_build(Thresholds, raw.get("thresholds"), "thresholds"),
        jev=_build(JevSettings, raw.get("jev"), "jev"),
        signals=_build(Signals, raw.get("signals"), "signals"),
        output=_build(Output, raw.get("output"), "output"),
        summaries=_build(Summaries, raw.get("summaries"), "summaries"),
        screening=_build_screening(raw.get("screening")),
        base_dir=base_dir or Path("."),
    )
    validate(config)
    return config


def _build_screening(table: Any) -> Screening:
    """[screening] holds two arrays of tables, so the criteria are built separately."""
    if table is None:
        return Screening()
    if not isinstance(table, dict):
        raise ConfigError("[screening] must be a table")
    criteria = {
        "include": [_build(Criterion, item, "screening.include") for item in table.get("include", [])],
        "exclude": [_build(Criterion, item, "screening.exclude") for item in table.get("exclude", [])],
    }
    scalars = {k: v for k, v in table.items() if k not in ("include", "exclude")}
    allowed = {f.name for f in fields(Screening)} - {"include", "exclude"}
    unknown = sorted(set(scalars) - allowed)
    if unknown:
        raise ConfigError(f"Unknown key(s) in [screening]: {', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}")
    return Screening(**scalars, **criteria)


def validate(config: Config) -> None:
    screening = config.screening
    if not config.interests and not screening.enabled:
        raise ConfigError("Add at least one [[interests]] entry: a plain-English statement about papers you want.")
    if not config.sources:
        raise ConfigError("Add at least one [[sources]] entry (for example type = \"arxiv\").")

    if screening.enabled:
        if not screening.include:
            raise ConfigError(
                "[screening] is enabled but has no [[screening.include]] criteria. "
                "Every include criterion must hold for a record to be eligible."
            )
        if screening.combine not in SCREEN_COMBINE:
            raise ConfigError(f"screening.combine must be one of {sorted(SCREEN_COMBINE)}")
        if not 0.5 <= screening.target_recall <= 1:
            raise ConfigError("screening.target_recall must be between 0.5 and 1")
        for name in ("threshold", "exclude_threshold"):
            if not 0 <= getattr(screening, name) <= 1:
                raise ConfigError(f"screening.{name} must be between 0 and 1")

    seen: set[str] = set()
    for item in [*config.interests, *config.exclusions, *screening.include, *screening.exclude]:
        if not ID_RE.match(item.id):
            raise ConfigError(f"id {item.id!r} must match [a-z0-9_]{{1,40}}")
        if item.id in seen:
            raise ConfigError(f"Duplicate id {item.id!r} across [[interests]] and [[exclude]]")
        seen.add(item.id)
        if not item.text.strip():
            raise ConfigError(f"{item.id}: text must not be empty")
    for interest in config.interests:
        if not 0 < interest.weight <= 1:
            raise ConfigError(f"{interest.id}: weight must be in (0, 1]")

    t = config.thresholds
    for name in ("must_read", "maybe", "exclude"):
        value = getattr(t, name)
        if not 0 <= value <= 1:
            raise ConfigError(f"thresholds.{name} must be between 0 and 1")
    if t.maybe > t.must_read:
        raise ConfigError("thresholds.maybe must be <= thresholds.must_read")

    if config.jev.backend not in BACKENDS:
        raise ConfigError(f"jev.backend must be one of {sorted(BACKENDS)}")
    if not 1 <= config.jev.concurrency <= 64:
        raise ConfigError("jev.concurrency must be between 1 and 64")
    if config.jev.requests_per_minute < 1:
        raise ConfigError("jev.requests_per_minute must be >= 1")
    if config.combine not in COMBINE_MODES:
        raise ConfigError(f"radar.combine must be one of {sorted(COMBINE_MODES)}")
    if config.max_papers < 1:
        raise ConfigError("radar.max_papers must be >= 1")

    if config.output.dedupe_days < 1 or config.output.feed_days < 1 or config.output.near_misses < 0:
        raise ConfigError("output.dedupe_days and output.feed_days must be >= 1, near_misses >= 0")
    if config.output.feedback_repo and not re.match(r"^[\w.-]+/[\w.-]+$", config.output.feedback_repo):
        raise ConfigError('output.feedback_repo must look like "owner/name"')
    if config.jev.price_per_mtok < 0:
        raise ConfigError("jev.price_per_mtok must be >= 0")
    if config.summaries.enabled and config.summaries.top_k < 1:
        raise ConfigError("summaries.top_k must be >= 1")

    for index, source in enumerate(config.sources):
        kind = source.get("type")
        if kind not in SOURCE_TYPES:
            raise ConfigError(f"sources[{index}].type must be one of {sorted(SOURCE_TYPES)}")
        allowed = SOURCE_KEYS[kind] | {"type", "name", "file"}
        unknown = sorted(set(source) - allowed)
        if unknown:
            raise ConfigError(
                f"Unknown key(s) in sources[{index}] ({kind}): {', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}"
            )
        if kind == "rss" and not (source.get("url") or source.get("file")):
            raise ConfigError(f"sources[{index}] (rss) needs a url")
        if kind == "pubmed" and not (source.get("query") or source.get("file")):
            raise ConfigError(
                f'sources[{index}] (pubmed) needs a query, for example '
                'query = \'"atrial fibrillation"[Title/Abstract]\''
            )


def lint(config: Config) -> list[str]:
    """Warnings based on Jev 1.13's documented jaggedness. Non-fatal."""
    warnings: list[str] = []
    for interest in config.interests:
        if NEGATION_RE.search(interest.text):
            warnings.append(
                f"interest '{interest.id}' contains a negation. Jev reads negations literally; "
                "move the negative part into an [[exclude]] entry phrased positively."
            )
        if len(interest.text) > 300:
            warnings.append(f"interest '{interest.id}' is long. Keep one idea per interest; split it into several.")
        if re.search(r"\band/or\b", interest.text):
            warnings.append(f"interest '{interest.id}' uses 'and/or'. Split it into two interests.")
        if re.search(r"\d{4}-\d{2}-\d{2}|\b(after|before|since)\s+\d{4}\b", interest.text):
            warnings.append(f"interest '{interest.id}' mentions dates. Jev is unreliable with date comparisons; filter dates in code.")
    for exclusion in config.exclusions:
        if NEGATION_RE.search(exclusion.text):
            warnings.append(f"exclude '{exclusion.id}' contains a negation. State what the paper IS about, positively.")
    for criterion in config.screening.include:
        if NEGATION_RE.search(criterion.text):
            warnings.append(
                f"screening.include '{criterion.id}' contains a negation. An include criterion should say what "
                "an eligible study IS; put the negative side in [[screening.exclude]], phrased positively."
            )
    for index, source in enumerate(config.sources):
        if source.get("type") == "arxiv" and not source.get("categories") and not source.get("file"):
            warnings.append(f"sources[{index}] (arxiv) has no categories, so only cs.AI is fetched. Add categories, or [\"*\"] for all of arXiv.")
        if source.get("type") == "pubmed" and not source.get("email") and not source.get("file"):
            warnings.append(f"sources[{index}] (pubmed): NCBI asks callers to identify themselves. Add email = \"you@example.com\".")
    if len(config.interests) + len(config.exclusions) > 30:
        warnings.append("More than 30 interests/exclusions: every one is a question on every paper, so cost scales with it.")
    return warnings
