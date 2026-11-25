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


KS = (50, 100, 150, 200, 250, 300)


def free_rules():
    """Rules that need nothing fitted."""
    rules = [(f"consecutive k={k}", partial(stop_consecutive, k=k)) for k in KS]
    for k in (50, 100):
        for frac in (0.1, 0.2, 0.3, 0.5):
            rules.append((f"dry run max({k}, {frac:.0%} of read)", partial(stop_consecutive, k=k, frac=frac)))
    for k in (30, 50, 100):
        for size in (0.03, 0.05, 0.08, 0.12):
            rules.append((f"dry run max({k}, {size:.0%} of review)", partial(stop_consecutive, k=k, size_frac=size)))
    rules.append(("knee (adjusted, min 150 read)", partial(stop_knee, min_read=150, every=10)))
    rules.append(("target t=10 (mean of 20 samples)", ("target", 10)))
    return rules


def floor_rules(floor: float):
    """Rules that use a threshold fitted on other reviews. Names carry no number, so the
    same rule can be compared across folds that fit different thresholds."""
    rules = [("fixed threshold (fitted on other reviews)", partial(stop_threshold, threshold=floor))]
    rules += [(f"consecutive k={k} + floor", partial(stop_consecutive, k=k, floor=floor)) for k in KS]
    return rules


def evaluate(topics, rules):
    names = sorted(topics)
    return {name: run_rule(topics, names, rule if isinstance(rule, tuple) else ("fn", rule)) for name, rule in rules}


def choose(results: dict[str, dict[str, Outcome]], fitting: list[str]) -> str:
    """Highest pooled WSS on the fitting reviews among rules that keep every one of them
    at or above the recall target. Falls back to the highest fitting recall."""
    scored = {name: pool([out[t] for t in fitting]) for name, out in results.items()}
    ok = [name for name, p in scored.items() if p["below"] == 0]
    if ok:
        return max(ok, key=lambda name: scored[name]["wss"])
    return max(scored, key=lambda name: (scored[name]["recall"], scored[name]["wss"]))


def loto_selection(topics) -> list[tuple[str, str, Outcome]]:
    """For each review: choose the rule on the other eleven, report it on this one."""
    names = sorted(topics)
    free = evaluate(topics, free_rules())
    picks = []
    for held in names:
        fitting = [t for t in names if t != held]
        floor = fit([r for t in fitting for r in topics[t]], TARGET)
        results = dict(free)
        results.update(evaluate(topics, floor_rules(floor)))
        rule = choose(results, fitting)
        picks.append((held, rule, results[rule][held]))
    return picks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("--fit-on", nargs="*", type=Path, default=None,
                        help="development topics; without it only the leave-one-review-out section is reported")
    parser.add_argument("--label", default="", help="model name for the report heading")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    warnings: list[str] = []
    topics = {}
    for d in args.dirs:
        topics.update(load_dir(d, warnings))
    if len(topics) < 2:
        print("need dumps for at least two topics", file=sys.stderr)
        return 2
    out = [f"# Stopping rules vs a fixed threshold{(' — ' + args.label) if args.label else ''}", ""]
    if args.fit_on:
        dev = set()
        for d in args.fit_on:
            dev |= set(load_dir(d, []))
        test = sorted(t for t in topics if t not in dev)
        dev = sorted(dev & set(topics))
        if not dev or not test:
            print("need both fitting and test topics", file=sys.stderr)
            return 2
        out += split_report(topics, dev, test)
    out += loto_report(topics)
    if warnings:
        out += ["", "## Warnings", ""] + [f"- {w}" for w in dict.fromkeys(warnings)]
    text = "\n".join(out) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text, end="")
    return 0


def split_report(topics, dev, test) -> list[str]:
    floor = fit([r for t in dev for r in topics[t]], TARGET)
    rules = floor_rules(floor) + free_rules()
    evaluated = evaluate(topics, rules)
    results = [(name, {t: out[t] for t in dev}, {t: out[t] for t in test}) for name, out in evaluated.items()]
    chosen = choose(evaluated, dev)

    out = [f"Reviewer reads each review in order of eligibility. Recall target {TARGET:.0%}. "
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
            "sample and every record without an abstract (always read, never ranked).",
            "", f"Fixed threshold and floor: {floor:.3f}, fitted on the development reviews."]
    return out


def loto_report(topics) -> list[str]:
    out = []
    picks = loto_selection(topics)
    fixed = []
    for held, _, _ in picks:
        fitting = [t for t in topics if t != held]
        thr = fit([r for t in fitting for r in topics[t]], TARGET)
        fixed.append(run_rule(topics, [held], ("fn", partial(stop_threshold, threshold=thr)))[held])
    pl, pf = pool([o for _, _, o in picks]), pool(fixed)
    out += ["", "## Leave one review out: rule chosen on the other reviews", "",
            "The rule is chosen with the same criterion as above, but on all the other reviews, then",
            "applied to the one left out. Nothing about the scored review is used to pick its rule.", "",
            "| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |",
            "|---|---|--:|--:|--:|--:|"]
    for (held, rule, o), f in zip(picks, fixed):
        out.append(f"| `{held}` | {rule} | {o.recall:.1%} | {o.wss:.1%} | {f.recall:.1%} | {f.wss:.1%} |")
    out += ["", "```",
            f"chosen rule      recall {pl['recall']:.1%} (95% CI {pl['lo']:.1%}–{pl['hi']:.1%}, {pl['found']}/{pl['eligible']}) "
            f"· pooled WSS {pl['wss']:.1%} · reviews below 95%: {pl['below']}",
            f"fixed threshold  recall {pf['recall']:.1%} (95% CI {pf['lo']:.1%}–{pf['hi']:.1%}, {pf['found']}/{pf['eligible']}) "
            f"· pooled WSS {pf['wss']:.1%} · reviews below 95%: {pf['below']}",
            "```"]
    return out


if __name__ == "__main__":
    raise SystemExit(main())
