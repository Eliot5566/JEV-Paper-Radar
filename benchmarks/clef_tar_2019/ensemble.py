#!/usr/bin/env python3
"""Average several models' scores per record and write them as one dump.

    python benchmarks/clef_tar_2019/ensemble.py dumps/jev/v2 dumps/claude/v2 --out dumps/jev+claude/v2

Each input is a directory of `run.py --dump` CSVs for the same topics. A record's
score in each model is what loto.py ranks by (exclusion criterion fired -> 0, no
abstract -> kept for a human); the output's eligibility is their mean. Records any
model could not judge stay "manual". The output reads like any other dump, so
loto.py and stopping.py take it unchanged. No model is called.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from loto import load_dir  # noqa: E402


def combine(dirs: list[Path], out: Path) -> int:
    warnings: list[str] = []
    models = [load_dir(d, warnings) for d in dirs]
    topics = set(models[0])
    for m in models[1:]:
        topics &= set(m)
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for topic in sorted(topics):
        per_model = [{r.pmid: r for r in m[topic]} for m in models]
        shared = set(per_model[0])
        for m in per_model[1:]:
            shared &= set(m)
        with (out / f"{topic}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["topic", "pmid", "label", "verdict", "eligibility", "triggered"])
            for pmid in sorted(shared):
                records = [m[pmid] for m in per_model]
                manual = any(not r.judged for r in records)
                score = 1.0 if manual else sum(r.score for r in records) / len(records)
                writer.writerow([topic, pmid, "1" if records[0].label else "0",
                                 "manual" if manual else "include", f"{score:.4f}", ""])
                written += 1
    for w in dict.fromkeys(warnings):
        print(f"warning: {w}", file=sys.stderr)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if len(args.dirs) < 2:
        print("need at least two dump directories", file=sys.stderr)
        return 2
    n = combine(args.dirs, args.out)
    print(f"wrote {n:,} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
