"""Append-only audit trail kept in the repo (`data/`).

* `decisions/<day>.jsonl`          full records for must-read and maybe papers
* `decisions/<day>.rest.jsonl.gz`  compact records for everything else (keeps git small)
* `screening/<day>.jsonl`          every screened record, kept in full (see below)
* `runs.jsonl`                     one line per run: counts, tokens, cost, model, time
* `labels.jsonl`                   your yes/no feedback, used by `paper-radar calibrate`
* `quarantine.jsonl`               papers that failed repeatedly: id, failure count,
                                  first/last failed day, last reason, quarantined_until

Screening records are never split or compressed: a systematic review has to be able to
account for every record it saw, including the ones the tool said no to.

Deduplication reads ids from the last `dedupe_days` of decision files, so there is no
ever-growing "seen" file rewritten on every run. Quarantined papers are skipped the
same way, for 30 days after their third consecutive failure, so a paper the model
cannot judge stops costing a call every morning.
"""

from __future__ import annotations

import gzip
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from .scoring import Decision

SHOWN_BANDS = {"must_read", "maybe"}

# A paper that fails this many days in a row is quarantined for this long,
# instead of being retried (and billed) every morning.
QUARANTINE_AFTER = 3
QUARANTINE_DAYS = 30


class Store:
    def __init__(self, data_dir: Path):
        self.root = data_dir
        self.decisions_dir = data_dir / "decisions"
        self.screening_dir = data_dir / "screening"
        self.runs_path = data_dir / "runs.jsonl"
        self.labels_path = data_dir / "labels.jsonl"
        self.quarantine_path = data_dir / "quarantine.jsonl"

    def load_usage(self) -> list[dict[str, Any]]:
        path = self.root / "usage.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

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

    def clear_day(self, day: str) -> int:
        """Forget one day's decisions so they can be judged again.

        Used by `run --rejudge` after the criteria change: today's items are inside the
        dedupe window, so without this a rerun judges nothing and the page keeps showing
        verdicts from the old config. Returns how many files were removed.
        """
        removed = 0
        for path in (self._full(day), self._rest(day)):
            if path.exists():
                path.unlink()
                removed += 1
        # A changed config may fix what made a paper fail, so rejudging a day
        # also gives its quarantined papers a fresh chance.
        if self.quarantine_path.exists():
            records = self.load_quarantine()
            kept = {k: v for k, v in records.items() if v.get("last_failed") != day}
            if len(kept) != len(records):
                self._write_quarantine(kept)
        return removed

    def seen_ids(self, today: date, window_days: int) -> set[str]:
        cutoff = (today - timedelta(days=window_days)).isoformat()
        ids: set[str] = set()
        for day in self.days():
            if day >= cutoff:
                ids.update(d.paper.id for d in self.load_decisions(day))
        return ids

    # ----------------------------------------------------------------- quarantine

    def load_quarantine(self) -> dict[str, dict[str, Any]]:
        """Papers that failed repeatedly: {id: {failures, first_failed, last_failed, last_reason, quarantined_until}}."""
        records: dict[str, dict[str, Any]] = {}
        if self.quarantine_path.exists():
            with self.quarantine_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        record = json.loads(line)
                        records[str(record["id"])] = record
        return records

    def _write_quarantine(self, records: dict[str, dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.quarantine_path.open("w", encoding="utf-8") as handle:
            for record in sorted(records.values(), key=lambda r: str(r["id"])):
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def quarantined_ids(self, today: date) -> set[str]:
        """Ids to skip this run: failed QUARANTINE_AFTER times and still in the window."""
        now = today.isoformat()
        return {
            paper_id
            for paper_id, record in self.load_quarantine().items()
            if record.get("quarantined_until") and record["quarantined_until"] >= now
        }

    def record_failures(self, day: str, failures: list[tuple[Any, str]]) -> list[str]:
        """Count today's failures; quarantine a paper after QUARANTINE_AFTER of them.

        Returns the ids newly quarantined by this call. A quarantined paper is
        skipped for QUARANTINE_DAYS, then gets one fresh attempt; a further
        failure quarantines it again.
        """
        records = self.load_quarantine()
        newly: list[str] = []
        for paper, reason in failures:
            record = records.get(paper.id, {"id": paper.id, "failures": 0, "first_failed": day})
            record["failures"] = int(record.get("failures") or 0) + 1
            record["last_failed"] = day
            record["last_reason"] = reason
            until = str(record.get("quarantined_until") or "")
            if record["failures"] >= QUARANTINE_AFTER and until < day:
                record["quarantined_until"] = (date.fromisoformat(day) + timedelta(days=QUARANTINE_DAYS)).isoformat()
                newly.append(paper.id)
            records[paper.id] = record
        if failures:
            self._write_quarantine(records)
        return newly

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

    # ------------------------------------------------------------------ screening
    def _screening(self, day: str) -> Path:
        return self.screening_dir / f"{day}.jsonl"

    def write_screening(self, day: str, decisions: Iterable[Any]) -> None:
        """Every screened record is kept in full — a review has to account for all of them."""
        self.screening_dir.mkdir(parents=True, exist_ok=True)
        with self._screening(day).open("a", encoding="utf-8") as handle:
            for decision in decisions:
                handle.write(json.dumps(decision.to_dict(), ensure_ascii=False) + "\n")

    def load_screening(self, day: str) -> list[dict[str, Any]]:
        path = self._screening(day)
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def screening_days(self) -> list[str]:
        if not self.screening_dir.exists():
            return []
        return sorted(p.stem for p in self.screening_dir.glob("*.jsonl"))

    def screened_ids(self) -> set[str]:
        return {r["paper"]["id"] for day in self.screening_days() for r in self.load_screening(day)}

    def eligibility_index(self) -> dict[str, float]:
        """paper id -> eligibility score, across every screening run."""
        index: dict[str, float] = {}
        for day in self.screening_days():
            for record in self.load_screening(day):
                index[record["paper"]["id"]] = float(record["eligibility"])
        return index

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
