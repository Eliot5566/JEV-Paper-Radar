"""Append-only audit trail kept in the repo (`data/`).

* `decisions/<day>.jsonl`          full records for must-read and maybe papers
* `decisions/<day>.rest.jsonl.gz`  compact records for everything else (keeps git small)
* `runs.jsonl`                     one line per run: counts, tokens, cost, model, time
* `labels.jsonl`                   your yes/no feedback, used by `paper-radar calibrate`

Deduplication reads ids from the last `dedupe_days` of decision files, so there is no
ever-growing "seen" file rewritten on every run.
"""

from __future__ import annotations

import gzip
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from .scoring import Decision

SHOWN_BANDS = {"must_read", "maybe"}


class Store:
    def __init__(self, data_dir: Path):
        self.root = data_dir
        self.decisions_dir = data_dir / "decisions"
        self.runs_path = data_dir / "runs.jsonl"
        self.labels_path = data_dir / "labels.jsonl"

    # ------------------------------------------------------------------ decisions
    def _full(self, day: str) -> Path:
        return self.decisions_dir / f"{day}.jsonl"

    def _rest(self, day: str) -> Path:
        return self.decisions_dir / f"{day}.rest.jsonl.gz"

    def write_decisions(self, day: str, decisions: Iterable[Decision]) -> None:
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        shown = [d for d in decisions if d.band in SHOWN_BANDS]
        rest = [d for d in decisions if d.band not in SHOWN_BANDS]
        if shown:
            with self._full(day).open("a", encoding="utf-8") as handle:
                for d in shown:
                    handle.write(json.dumps(d.to_dict(full=True), ensure_ascii=False) + "\n")
        if rest:
            with gzip.open(self._rest(day), "at", encoding="utf-8") as handle:
                for d in rest:
                    handle.write(json.dumps(d.to_dict(full=False), ensure_ascii=False) + "\n")

    def load_decisions(self, day: str) -> list[Decision]:
        records: list[dict[str, Any]] = []
        if self._full(day).exists():
            with self._full(day).open(encoding="utf-8") as handle:
                records.extend(json.loads(line) for line in handle if line.strip())
        if self._rest(day).exists():
            with gzip.open(self._rest(day), "rt", encoding="utf-8") as handle:
                records.extend(json.loads(line) for line in handle if line.strip())
        return [Decision.from_dict(r) for r in records]

    def days(self) -> list[str]:
        if not self.decisions_dir.exists():
            return []
        names = {p.name.split(".")[0] for p in self.decisions_dir.iterdir() if p.name[:4].isdigit()}
        return sorted(names)

    def seen_ids(self, today: date, window_days: int) -> set[str]:
        cutoff = (today - timedelta(days=window_days)).isoformat()
        ids: set[str] = set()
        for day in self.days():
            if day >= cutoff:
                ids.update(d.paper.id for d in self.load_decisions(day))
        return ids

    # ----------------------------------------------------------------------- runs
    def append_run(self, summary: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.runs_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False) + "\n")

    def load_runs(self) -> list[dict[str, Any]]:
        if not self.runs_path.exists():
            return []
        with self.runs_path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    # --------------------------------------------------------------------- labels
    def add_label(self, paper_id: str, relevant: bool, when: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.labels_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"id": paper_id, "relevant": relevant, "at": when}) + "\n")

    def load_labels(self) -> dict[str, bool]:
        labels: dict[str, bool] = {}
        if self.labels_path.exists():
            with self.labels_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        record = json.loads(line)
                        labels[record["id"]] = bool(record["relevant"])
        return labels

    def relevance_index(self) -> dict[str, float]:
        index: dict[str, float] = {}
        for day in self.days():
            for d in self.load_decisions(day):
                index[d.paper.id] = d.relevance
        return index
