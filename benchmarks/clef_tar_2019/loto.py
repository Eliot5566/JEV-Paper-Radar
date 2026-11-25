#!/usr/bin/env python3
"""Honest screening numbers from per-record dumps: thresholds fitted on *other* reviews.

    python benchmarks/clef_tar_2019/run.py --criteria v2 --dump dumps/v2 --email you@example.com
    python benchmarks/clef_tar_2019/run.py --criteria holdout --dump dumps/holdout --email you@example.com
    python benchmarks/clef_tar_2019/loto.py dumps/v2 dumps/holdout --fit-on dumps/v2 --out loto.md

`run.py` fits the threshold on the same judgments it scores, which answers "how
well could this separate eligible studies if the threshold were tuned perfectly?"
A team screening its next review cannot do that: it has to pick the threshold
before it has any labels. This script measures that case. No model is called; it
only reads the CSVs that `run.py --dump` writes.

Two fitting modes:

* Leave-one-topic-out (default): each topic is scored with a threshold fitted on
  all the *other* topics.
* ``--fit-on DIR``: the threshold is fitted once on the topics in DIR (e.g. the
  eight development reviews) and applied to every other topic (e.g. the four
  held-out ones). This is the closest to "what it will do on your next review".

Two ways to turn several reviews into one threshold, both reported:

* ``pooled``: the threshold that reaches the recall target on all the fitting
  topics' records put together.
* ``min``: the lowest of the fitting topics' own thresholds. More conservative:
  more reading, fewer misses.

Also reported: a Wilson 95% interval for pooled recall (with ~100 eligible
studies the interval is several points wide, and that belongs next to the
headline), and a reliability table with Brier score and ECE for the eligibility
score. The eligibility score is the criteria's probabilities combined, not a
probability that a human includes the record, so read the calibration table as
"how far is this score from a probability", not as a defect in any one model.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from paper_radar.screening import screening_performance  # noqa: E402


@dataclass
class Record:
    topic: str
    pmid: str
    label: bool
    score: float     # what the threshold is compared with
    judged: bool     # False for no-abstract records, which always go to a human


def load_dump(path: Path, warnings: list[str]) -> list[Record]:
    """One dump CSV -> records, scored the way run.py scores them."""
    records: list[Record] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        has_triggered = "triggered" in (reader.fieldnames or [])
        if not has_triggered:
            warnings.append(
                f"{path.name}: no 'triggered' column (dumped before it existed). Records excluded by an "
                "exclusion criterion are scored by their eligibility instead of 0, which can only make "
                "recall look higher. Re-dump with the current run.py for exact numbers."
            )
        for row in reader:
            if row.get("label", "") == "":
                continue
            verdict = row["verdict"]
            if verdict == "manual":
                score, judged = 1.0, False
            elif has_triggered and row["triggered"]:
                score, judged = 0.0, True
            else:
                score, judged = float(row["eligibility"]), True
            records.append(Record(row["topic"], row["pmid"], row["label"] == "1", score, judged))
    return records


def load_dir(directory: Path, warnings: list[str]) -> dict[str, list[Record]]:
    topics: dict[str, list[Record]] = {}
    for path in sorted(directory.glob("*.csv")):
        rows = load_dump(path, warnings)
        if rows:
            topics[rows[0].topic] = rows
    return topics


def fit(records: list[Record], target: float) -> float | None:
    perf = screening_performance({r.pmid + "@" + r.topic: r.score for r in records},
                                 {r.pmid + "@" + r.topic: r.label for r in records}, target_recall=target)
    return perf.threshold if perf.positives else None


def apply(records: list[Record], threshold: float) -> dict[str, float]:
    n = len(records)
    pos = sum(r.label for r in records)
    found = sum(1 for r in records if r.label and r.score >= threshold)
    kept = sum(1 for r in records if r.score >= threshold)
    recall = found / pos if pos else float("nan")
    return {"n": n, "eligible": pos, "found": found, "kept": kept, "recall": recall,
            "wss": (n - kept) / n - (1 - recall) if n and pos else float("nan")}


def wilson(found: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if not total:
        return float("nan"), float("nan")
    p = found / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - half), min(1.0, centre + half)


def reliability(records: list[Record], bins: int = 10) -> tuple[list[tuple], float, float]:
    pairs = [(r.score, 1 if r.label else 0) for r in records if r.judged]
    rows, ece = [], 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [(p, y) for p, y in pairs if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if bucket:
            mean_p = sum(p for p, _ in bucket) / len(bucket)
            rate = sum(y for _, y in bucket) / len(bucket)
            ece += len(bucket) / len(pairs) * abs(mean_p - rate)
            rows.append((lo, hi, len(bucket), mean_p, rate))
    brier = sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else float("nan")
    return rows, brier, ece


def analyse(topics: dict[str, list[Record]], fit_topics: set[str] | None, target: float) -> dict:
    own = {t: fit(rows, target) for t, rows in topics.items()}
    tested = sorted(t for t in topics if fit_topics is None or t not in fit_topics)
    results = {}
    for mode in ("pooled", "min"):
        per_topic = []
        for topic in tested:
            fitting = [t for t in topics if t != topic and (fit_topics is None or t in fit_topics)]
            if mode == "pooled":
                threshold = fit([r for t in fitting for r in topics[t]], target)
            else:
                candidates = [own[t] for t in fitting if own[t] is not None]
                threshold = min(candidates) if candidates else None
            if threshold is None:
                continue
            per_topic.append((topic, threshold, apply(topics[topic], threshold)))
        results[mode] = per_topic
    in_sample = [(t, own[t], apply(topics[t], own[t])) for t in tested if own[t] is not None]
    return {"tested": tested, "own": own, "modes": results, "in_sample": in_sample}


def pooled(per_topic: list[tuple]) -> dict[str, float]:
    n = sum(m["n"] for _, _, m in per_topic)
    eligible = sum(m["eligible"] for _, _, m in per_topic)
    found = sum(m["found"] for _, _, m in per_topic)
    kept = sum(m["kept"] for _, _, m in per_topic)
    recall = found / eligible if eligible else float("nan")
    wss = (n - kept) / n - (1 - recall) if n else float("nan")
    lo, hi = wilson(found, eligible)
    return {"n": n, "eligible": eligible, "found": found, "recall": recall, "wss": wss, "lo": lo, "hi": hi}


def render(topics, result, fit_dirs, target, warnings) -> str:
    out = ["# Screening with thresholds fitted on other reviews", ""]
    how = ("fitted once on " + ", ".join(str(d) for d in fit_dirs) + ", applied to every other topic"
           if fit_dirs else "leave-one-topic-out: each topic scored with a threshold fitted on the others")
    out += [f"Recall target {target:.0%} · {how}.", ""]
    out += ["| Topic | Records | Eligible | own threshold (optimistic) | recall | WSS | "
            "pooled threshold | recall | WSS | min threshold | recall | WSS |",
            "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    by_mode = {mode: {t: (thr, m) for t, thr, m in rows} for mode, rows in result["modes"].items()}
    for topic, own_thr, m in result["in_sample"]:
        cells = [f"`{topic}`", f"{m['n']:,}", str(m["eligible"]), f"{own_thr:.3f}", f"{m['recall']:.1%}", f"{m['wss']:.1%}"]
        for mode in ("pooled", "min"):
            if topic in by_mode[mode]:
                thr, mm = by_mode[mode][topic]
                cells += [f"{thr:.3f}", f"{mm['recall']:.1%}", f"{mm['wss']:.1%}"]
            else:
                cells += ["–", "–", "–"]
        out.append("| " + " | ".join(cells) + " |")
    out += ["", "```"]
    for label, rows in [("own (optimistic)", result["in_sample"]), ("pooled", result["modes"]["pooled"]),
                        ("min", result["modes"]["min"])]:
        if rows:
            p = pooled(rows)
            out.append(f"{label:<17} recall {p['recall']:.1%} (95% CI {p['lo']:.1%}–{p['hi']:.1%}, "
                       f"{p['found']}/{p['eligible']}) · pooled WSS {p['wss']:.1%}")
    out += ["```", ""]
    tested_records = [r for t in result["tested"] for r in topics[t]]
    rows, brier, ece = reliability(tested_records)
    out += ["## Calibration of the eligibility score (tested topics, judged records)", "",
            f"Brier {brier:.3f} · ECE {ece:.3f}", "",
            "| Score bin | Records | Mean score | Share eligible |", "|---|--:|--:|--:|"]
    out += [f"| {lo:.1f}–{hi:.1f} | {n:,} | {mp:.3f} | {rate:.3f} |" for lo, hi, n, mp, rate in rows]
    out += ["", "The eligibility score combines the criteria's probabilities; it is not a calibrated "
            "probability of inclusion, so a gap here is expected and is what a threshold fitted on "
            "labels corrects for."]
    if warnings:
        out += ["", "## Warnings", ""] + [f"- {w}" for w in dict.fromkeys(warnings)]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", type=Path, help="directories of run.py --dump CSVs")
    parser.add_argument("--fit-on", nargs="*", type=Path, default=None,
                        help="fit on the topics in these directories and test on the rest")
    parser.add_argument("--recall", type=float, default=0.95)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    warnings: list[str] = []
    topics: dict[str, list[Record]] = {}
    for directory in args.dirs:
        topics.update(load_dir(directory, warnings))
    fit_topics = None
    if args.fit_on:
        fit_topics = set()
        for directory in args.fit_on:
            fit_topics |= set(load_dir(directory, []))
    if len(topics) < 2:
        print("need dumps for at least two topics", file=sys.stderr)
        return 2
    result = analyse(topics, fit_topics, args.recall)
    if not result["tested"]:
        print("no topics left to test after --fit-on", file=sys.stderr)
        return 2
    text = render(topics, result, args.fit_on, args.recall, warnings)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
