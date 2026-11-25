#!/usr/bin/env python3
"""How much reading do stopping rules save, compared with a fixed threshold?

    python benchmarks/clef_tar_2019/stopping.py dumps/v2 dumps/holdout --fit-on dumps/v2 --out stopping.md

Reads the CSVs `run.py --dump` writes, simulates a reviewer reading each review in
order of eligibility (highest first) and stopping when a rule says so, and reports
recall and work saved (WSS, counting every record the reviewer read).

Honesty: rule settings are chosen on the `--fit-on` topics only (the development
reviews) and then reported on the others, the same split loto.py uses. The full grid
is printed too, so nobody has to take the choice on trust.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from loto import fit, load_dir, wilson  # noqa: E402
from paper_radar.stopping import (  # noqa: E402
    Outcome, simulate, simulate_target, stop_consecutive, stop_knee, stop_threshold,
)

TARGET = 0.95


def ordered(records):
    """Judged records in reading order. Records without an abstract are left out: a
    reviewer reads them regardless, and their labels say nothing about the ranking."""
    rows = sorted((r for r in records if r.judged), key=lambda r: (-r.score, r.pmid))
    return [r.score for r in rows], [r.label for r in rows]


def with_manual(outcome: Outcome, records) -> Outcome:
    manual = [r for r in records if not r.judged]
    hits = sum(r.label for r in manual)
    return Outcome(outcome.read + len(manual), outcome.found + hits, outcome.total + len(manual),
                   outcome.eligible + hits)


def pool(outcomes: list[Outcome]) -> dict:
    total = sum(o.total for o in outcomes)
    read = sum(o.read for o in outcomes)
    eligible = sum(o.eligible for o in outcomes)
    found = sum(o.found for o in outcomes)
    recall = found / eligible if eligible else float("nan")
    lo, hi = wilson(found, eligible)
    return {"recall": recall, "lo": lo, "hi": hi, "wss": (total - read) / total - (1 - recall),
            "worst": min(o.recall for o in outcomes), "below": sum(o.recall < TARGET for o in outcomes),
            "found": found, "eligible": eligible, "read": read, "total": total}


def run_rule(topics, names, rule) -> dict[str, Outcome]:
    out = {}
    for name in names:
        scores, labels = ordered(topics[name])
        if rule[0] == "target":
            runs = [simulate_target(labels, t=rule[1], seed=s) for s in range(20)]
            out[name] = Outcome(round(sum(o.read for o in runs) / len(runs)), round(sum(o.found for o in runs) / len(runs)),
                                len(labels), sum(labels))
        else:
            out[name] = simulate(scores, labels, rule[1])
        out[name] = with_manual(out[name], topics[name])
    return out


def grid(floor: float):
    rules = []
    for k in (50, 100, 150, 200, 300):
        rules.append((f"consecutive k={k}", partial(stop_consecutive, k=k)))
        rules.append((f"consecutive k={k} + floor {floor:.3f}", partial(stop_consecutive, k=k, floor=floor)))
    for k in (20, 50):
        for frac in (0.1, 0.2, 0.3, 0.5):
            rules.append((f"dry run max({k}, {frac:.0%} of read)", partial(stop_consecutive, k=k, frac=frac)))
    rules.append(("knee (adjusted, min 150 read)", partial(stop_knee, min_read=150, every=10)))
    rules.append(("target t=10 (mean of 20 samples)", ("target", 10)))
    return rules


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("--fit-on", nargs="*", type=Path, required=True)
    parser.add_argument("--label", default="", help="model name for the report heading")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    warnings: list[str] = []
    topics = {}
    for d in args.dirs:
        topics.update(load_dir(d, warnings))
    dev = set()
    for d in args.fit_on:
        dev |= set(load_dir(d, []))
    test = sorted(t for t in topics if t not in dev)
    dev = sorted(dev & set(topics))
    if not dev or not test:
        print("need both fitting and test topics", file=sys.stderr)
        return 2

    floor = fit([r for t in dev for r in topics[t]], TARGET)
    rules = [(f"fixed threshold {floor:.3f} (fitted on dev)", partial(stop_threshold, threshold=floor))] + grid(floor)
    results = []
    for name, rule in rules:
        r = rule if isinstance(rule, tuple) else ("fn", rule)
        d_out, t_out = run_rule(topics, dev, r), run_rule(topics, test, r)
        results.append((name, d_out, t_out))

    # Choose on dev only: highest dev WSS among rules with every dev topic at or above target.
    ok = [(name, pool(list(d.values()))) for name, d, _ in results[1:]
          if pool(list(d.values()))["below"] == 0]
    chosen = max(ok, key=lambda x: x[1]["wss"])[0] if ok else None

    out = [f"# Stopping rules vs a fixed threshold{(' — ' + args.label) if args.label else ''}", "",
           f"Reviewer reads each review in order of eligibility. Recall target {TARGET:.0%}. "
           f"Development topics ({len(dev)}): settings chosen here. Test topics ({len(test)}): reported.", "",
           "| Rule | dev recall | dev WSS | dev topics < 95% | test recall (95% CI) | test WSS | test worst topic | test topics < 95% |",
           "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for name, d, t in results:
        pd, pt = pool(list(d.values())), pool(list(t.values()))
        mark = " **(chosen on dev)**" if name == chosen else ""
        out.append(f"| {name}{mark} | {pd['recall']:.1%} | {pd['wss']:.1%} | {pd['below']} | "
                   f"{pt['recall']:.1%} ({pt['lo']:.1%}–{pt['hi']:.1%}) | {pt['wss']:.1%} | {pt['worst']:.1%} | {pt['below']} |")
    out += ["", "## Per test topic", "", "| Rule | " + " | ".join(f"`{t}`" for t in test) + " |",
            "|---|" + "--:|" * len(test)]
    for name, _, t in results:
        if name == chosen or name == results[0][0] or name.startswith("knee") or name.startswith("target"):
            out.append(f"| {name} | " + " | ".join(f"{t[x].recall:.0%} / {t[x].wss:.0%}" for x in test) + " |")
    out += ["", "Cells are recall / WSS. WSS counts every record read, including the target method's random "
            "sample and every record without an abstract (always read, never ranked)."]
    if warnings:
        out += ["", "## Warnings", ""] + [f"- {w}" for w in dict.fromkeys(warnings)]
    text = "\n".join(out) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
