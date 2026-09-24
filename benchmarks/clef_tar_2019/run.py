#!/usr/bin/env python3
"""Measure Paper Radar's screening against CLEF TAR 2019 relevance judgments.

    python benchmarks/clef_tar_2019/run.py --backend mock      # free dry run
    python benchmarks/clef_tar_2019/run.py                     # the real thing

Why this dataset. CLEF eHealth's Technology Assisted Reviews track published, for each
of a set of real Cochrane reviews, the full set of records the review's Boolean search
returned together with the reviewers' own **title-and-abstract stage** judgments. That
last part is what makes it usable here: a dataset of final, post-full-text inclusions
would flatter the tool, because records a human passed at the abstract stage and only
rejected after reading the paper would be scored as correct exclusions.

Everything is cached under benchmarks/clef_tar_2019/cache/, so a rerun costs nothing
until the criteria or the model change. Fetching the abstracts is the slow step; NCBI
allows 3 requests a second without an API key, so the first run takes a few minutes.

Honest accounting, all of it visible in the output:

* Records PubMed no longer serves, or that arrive without an abstract, are counted and
  reported separately. They are never silently dropped and never counted as correct
  exclusions — a review has to account for every record it saw.
* Two of the eight reviews have an eligibility criterion that is a numeric comparison
  (a minimum trial duration, a minimum follow-up). Paper Radar's design rule is that
  the model is never asked to compare numbers, so those are deliberately not encoded.
  It costs precision on those topics, and the criteria files say so.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tomllib
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from paper_radar.cli import load_dotenv  # noqa: E402
from paper_radar.config import parse_config  # noqa: E402
from paper_radar.jev import make_backend  # noqa: E402
from paper_radar.models import Paper  # noqa: E402
from paper_radar.pipeline import judge_all  # noqa: E402
from paper_radar.questions import build_screening_questions  # noqa: E402
from paper_radar.screening import (  # noqa: E402
    INCLUDE, MANUAL, ScreenDecision, combine_criteria, screen, screening_performance,
)
from paper_radar.sources.pubmed import EUTILS, parse_pubmed  # noqa: E402

QRELS_URL = (
    "https://raw.githubusercontent.com/CLEF-TAR/tar/master/2019-TAR/Task2/Training/"
    "Intervention/qrels/full.train.int.abs.2019.qrels"
)
CACHE = HERE / "cache"
BATCH = 200
# Both aggregation rules are scored from the same answers, so the comparison is paired.
COMBINE_MODES = ("geometric", "min")


def load_qrels() -> dict[str, dict[str, int]]:
    """topic -> {pmid: 0|1}, from the track's abstract-level judgments."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "qrels.txt"
    if not path.exists():
        print(f"downloading qrels from {QRELS_URL}")
        with urllib.request.urlopen(QRELS_URL, timeout=60) as response:
            path.write_bytes(response.read())
    judged: dict[str, dict[str, int]] = defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 4:
            topic, _, pmid, relevance = parts
            judged[topic][pmid] = int(relevance)
    return judged


def fetch_records(pmids: list[str], email: str, api_key: str) -> dict[str, dict]:
    """PMID -> {title, abstract}, cached on disk. The slow step; resumable."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "records.json"
    known: dict[str, dict] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    missing = [p for p in pmids if p not in known]
    if not missing:
        return known

    pause = 0.11 if api_key else 0.34
    print(f"fetching {len(missing):,} abstracts from PubMed ({len(missing) // BATCH + 1} batches)")
    for index in range(0, len(missing), BATCH):
        chunk = missing[index : index + BATCH]
        params = {"db": "pubmed", "id": ",".join(chunk), "retmode": "xml", "tool": "paper-radar-benchmark"}
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key
        url = f"{EUTILS}/efetch.fcgi?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=120) as response:
            xml = response.read().decode("utf-8", "replace")
        # exclude_types is empty on purpose: the reviewers judged these records, errata
        # included, so dropping any of them here would change the denominator.
        for paper in parse_pubmed(xml, set()):
            known[paper.id.split(":", 1)[1]] = {"title": paper.title, "abstract": paper.abstract}
        for pmid in chunk:                       # record the misses too, so they are not refetched
            known.setdefault(pmid, {"title": "", "abstract": ""})
        path.write_text(json.dumps(known), encoding="utf-8")
        print(f"  {min(index + BATCH, len(missing)):>6,}/{len(missing):,}")
        time.sleep(pause)
    return known


def config_for(topic_file: Path):
    raw = tomllib.loads(topic_file.read_text(encoding="utf-8"))
    meta = raw.pop("benchmark", {})
    raw["jev"] = {"backend": "mock", "concurrency": 8}
    raw["sources"] = [{"type": "pubmed", "query": "placeholder"}]  # records are supplied directly
    return meta, parse_config(raw, base_dir=HERE)


def dump_scores(path: Path, topic: str, decisions, judged: dict[str, int]) -> None:
    """Every criterion's own probability, per record, next to the human label.

    The pooled metrics cannot tell you *why* a topic scored badly. This can: if one
    criterion sits near zero for the eligible studies too, the min() conjunction is
    throwing away the signal the other criteria found.
    """
    import csv

    criteria = sorted({k for d in decisions for k in d.include})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["topic", "pmid", "label", "verdict", "eligibility", "weakest", *criteria])
        for d in decisions:
            pmid = d.paper.id.split(":", 1)[1]
            writer.writerow([topic, pmid, judged.get(pmid, ""), d.verdict, round(d.eligibility, 4), d.weakest,
                             *[round(d.include.get(c, float("nan")), 4) for c in criteria]])


def run_topic(topic_file: Path, judged: dict[str, int], records: dict[str, dict], backend, target_recall: float,
              log=print, dump: Path | None = None):
    meta, config = config_for(topic_file)
    papers, gone = [], 0
    for pmid in judged:
        record = records.get(pmid)
        if not record or not record["title"]:
            gone += 1
            continue
        papers.append(Paper(id=f"pubmed:{pmid}", source="pubmed", title=record["title"],
                            abstract=record["abstract"], url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"))

    questions = build_screening_questions(config)
    # Records with no abstract never reach the model — that is what run_screening() does,
    # and sending them anyway would both cost money and misreport what the tool costs.
    sendable = [p for p in papers if p.abstract.strip()]
    skipped = [p for p in papers if not p.abstract.strip()]
    log(f"  {meta.get('topic', topic_file.stem)}: {len(papers):,} records, "
        f"{len(sendable):,} with an abstract to judge …")
    decisions, failures = judge_all(backend, sendable, questions, config, log=log, verdict=screen)
    decisions += [ScreenDecision(paper=p, verdict=MANUAL, eligibility=0.0, model=backend.model) for p in skipped]

    scores = {mode: {} for mode in COMBINE_MODES}
    no_abstract, free_hits = 0, 0
    for decision in decisions:
        pmid = decision.paper.id.split(":", 1)[1]
        if decision.verdict == MANUAL:
            no_abstract += 1
            # Goes to a human, so it counts as kept, not as saved work. When such a record
            # is one of the eligible studies, the model did not find it — a rule did. That
            # is counted separately below, because it otherwise inflates recall silently.
            free_hits += int(bool(judged[pmid]))
            for mode in COMBINE_MODES:
                scores[mode][pmid] = 1.0
        else:
            for mode in COMBINE_MODES:
                scores[mode][pmid] = 0.0 if decision.triggered else combine_criteria(
                    list(decision.include.values()), mode)
    labels = {pmid: bool(judged[pmid]) for pmid in scores["geometric"]}
    reports = {mode: screening_performance(scores[mode], labels, target_recall=target_recall)
               for mode in COMBINE_MODES}
    report = reports["geometric"]
    if dump is not None:
        dump_scores(dump / f"{meta.get('topic', topic_file.stem)}.csv", meta.get("topic", topic_file.stem),
                    decisions, judged)

    at_default = sum(1 for d in decisions if d.verdict == INCLUDE or d.verdict == MANUAL)
    return {
        "topic": meta.get("topic", topic_file.stem),
        "title": meta.get("review_title", ""),
        "judged": len(judged),
        "screened": len(decisions),
        "unavailable": gone,
        "failed": len(failures),
        "no_abstract": no_abstract,
        "free_hits": free_hits,
        "eligible": sum(judged.values()),
        "report": report,
        "reports": reports,
        "kept_at_default": at_default,
        "tokens": sum(d.input_tokens for d in decisions),
        "cost": sum(d.cost for d in decisions),
        "model": next((d.model for d in decisions if d.model), backend.model),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", default="typesafe", choices=["typesafe", "openrouter", "mock"])
    parser.add_argument("--recall", type=float, default=0.95, help="recall target the threshold is fitted to")
    parser.add_argument("--topics", nargs="*", help="only these topic ids")
    parser.add_argument("--email", default="", help="passed to NCBI, which asks callers to identify themselves")
    # A mock run never writes results.md. Its numbers are meaningless, and a stale one
    # left lying next to the real file is indistinguishable from a finished measurement.
    parser.add_argument("--criteria", default="v2", help="criteria set under criteria/ (v1 = literal, v2 = revised)")
    parser.add_argument("--dump", metavar="DIR", help="write per-criterion probabilities per record, for diagnosis")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if args.out is None:
        stem = "results.mock" if args.backend == "mock" else f"results.{args.criteria}"
        args.out = str(HERE / f"{stem}.md")

    import os
    # The CLI loads .env for you; this script does not go through the CLI, so it has to.
    load_dotenv(ROOT / ".env")
    load_dotenv(Path(".env"))
    api_key = os.environ.get("NCBI_API_KEY", "").strip()

    files = sorted((HERE / "criteria" / args.criteria).glob("*.toml"))
    if args.topics:
        wanted = set(args.topics)
        files = [f for f in files if f.stem in wanted]
    if not files:
        print("no criteria files matched", file=sys.stderr)
        return 2

    # Build the backend first. Downloading 8,000 abstracts and only then discovering
    # that the key is missing wastes several minutes of someone's afternoon.
    _, probe = config_for(files[0])
    probe.jev.backend = args.backend
    backend = make_backend(probe.jev)

    dump_dir = Path(args.dump) if args.dump else None
    if dump_dir:
        dump_dir.mkdir(parents=True, exist_ok=True)

    judged = load_qrels()
    needed = [pmid for f in files for pmid in judged.get(f.stem, {})]
    print(f"{len(files)} topics, {len(needed):,} judged records, backend {backend.name} ({backend.model})")
    records = fetch_records(needed, args.email, api_key)

    results = []
    for topic_file in files:
        started = time.monotonic()
        result = run_topic(topic_file, judged[topic_file.stem], records, backend, args.recall, dump=dump_dir)
        result["seconds"] = time.monotonic() - started
        results.append(result)
        r = result["report"]
        g, m = result["reports"]["geometric"], result["reports"]["min"]
        print(f"  {result['topic']}  n={result['screened']:>5,}  eligible={result['eligible']:>3}  "
              f"| geometric: recall={g.recall:>6.1%} WSS={g.workload_saved:>6.1%} "
              f"| min: recall={m.recall:>6.1%} WSS={m.workload_saved:>6.1%} | ${result['cost']:.4f}")

    Path(args.out).write_text(render(results, args), encoding="utf-8")
    print(f"\nwrote {args.out}  (model: {results[0]['model']})")
    for mode in COMBINE_MODES:
        print("  " + pooled_for(results, mode))
    return 0


def pooled_for(results: list[dict], mode: str) -> str:
    n = sum(r["screened"] for r in results)
    reports = [r["reports"][mode] for r in results]
    eligible = sum(rep.positives for rep in reports)
    found = sum(round(rep.recall * rep.positives) for rep in reports)
    saved = sum(rep.workload_saved * r["screened"] for r, rep in zip(results, reports))
    per_topic = sorted(rep.workload_saved for rep in reports)
    mid = len(per_topic) // 2
    median = per_topic[mid] if len(per_topic) % 2 else (per_topic[mid - 1] + per_topic[mid]) / 2
    return (f"{mode:<10} recall {found / eligible:>6.1%} · pooled WSS {saved / n:>6.1%} · "
            f"median WSS {median:>6.1%}")


def pooled_line(results: list[dict]) -> str:
    """Pooled over records, not averaged over topics: a 40-record review and a 5,000-record
    one do not deserve equal weight when the question is how much reading is saved."""
    n = sum(r["screened"] for r in results)
    eligible = sum(r["report"].positives for r in results)
    found = sum(round(r["report"].recall * r["report"].positives) for r in results)
    saved = sum(r["report"].workload_saved * r["screened"] for r in results)
    cost = sum(r["cost"] for r in results)
    return (f"Pooled: {n:,} records, {eligible} eligible, recall {found / eligible:.1%}, "
            f"WSS {saved / n:.1%}, ${cost:.2f} total")


def render(results: list[dict], args) -> str:
    lines = [
        "# CLEF TAR 2019 — measured screening performance",
        "",
        f"Model: `{results[0]['model']}` · criteria `{args.criteria}` · recall target {args.recall:.0%} · "
        f"generated {time.strftime('%Y-%m-%d')}",
        "",
        "Abstract-level relevance judgments from the CLEF eHealth Technology Assisted Reviews",
        "2019 track (Task 2, Intervention, training set). Criteria come from each review's own",
        "published selection criteria; see `criteria/*.toml`, which quote the source verbatim.",
        "",
        "Both aggregation rules are scored from the same Jev answers, so the comparison is",
        "paired: no record is judged twice and no run-to-run variation enters it.",
        "",
        "| Topic | Review | Records | Eligible | geometric recall | geometric WSS | min recall | min WSS | No abstract | Cost |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for r in results:
        g, m = r["reports"]["geometric"], r["reports"]["min"]
        lines.append(
            f"| `{r['topic']}` | {r['title'][:46]} | {r['screened']:,} | {g.positives} | "
            f"{g.recall:.1%} | **{g.workload_saved:.1%}** | {m.recall:.1%} | {m.workload_saved:.1%} | "
            f"{r['no_abstract']} | ${r['cost']:.4f} |"
        )
    lines += ["", "```",
              f"{'records':<10} {sum(r['screened'] for r in results):,}   "
              f"eligible {sum(r['reports']['geometric'].positives for r in results)}   "
              f"cost ${sum(r['cost'] for r in results):.2f}",
              pooled_for(results, "geometric"),
              pooled_for(results, "min"),
              "```", ""]
    free = sum(r["free_hits"] for r in results)
    eligible = sum(r["report"].positives for r in results)
    if free:
        lines += [
            f"**Free hits: {free} of the {eligible} eligible studies ({free / eligible:.0%}) had no abstract**, so "
            "they were kept by the no-abstract rule rather than found by the model. Recall would be "
            f"{(sum(round(r['report'].recall * r['report'].positives) for r in results) - free) / (eligible - free):.1%} "
            "counting only the studies the model actually judged.",
            "",
        ]

    unavailable = sum(r["unavailable"] for r in results)
    failed = sum(r["failed"] for r in results)
    if unavailable or failed:
        lines += [
            f"{unavailable:,} judged records could not be retrieved from PubMed and are excluded "
            f"from every figure above; {failed} request(s) failed.",
            "",
        ]
    lines += [
        "## How to read this",
        "",
        "`WSS` is work saved over sampling at the recall actually achieved: the share of records a",
        "reviewer would not have to read, minus what pure sampling at that recall would give for",
        "free. It is the metric this literature uses, so these numbers are comparable to published",
        "tools. Three things keep them from being better than they look:",
        "",
        "1. **The threshold is fitted per topic on the same judgments it is measured against.**",
        "   That is the optimistic case. It answers \"how well could this separate eligible studies",
        "   from the rest if you tuned it perfectly?\", not \"what will it do on your next review\".",
        "2. **Recall is achieved, not targeted.** The threshold is the lowest score among the",
        "   studies needed to reach the target, and you cannot keep a fraction of a study — so on",
        "   a topic with few eligible studies the target rounds up to 100% recall, which pushes WSS",
        "   down. Read the Recall column next to every WSS figure.",
        "3. **Free hits.** Records without an abstract are always kept, never counted as saved work.",
        "   When one of them is an eligible study, the model did not find it; a rule did. The",
        "   \"Free hits\" column counts those, and the line under the table restates recall without",
        "   them.",
        "",
        "## Reproducing",
        "",
        "```bash",
        f"python benchmarks/clef_tar_2019/run.py --criteria {args.criteria} --email you@example.com",
        "```",
        "",
        "Set `NCBI_API_KEY` to fetch faster. Everything is cached under `cache/`, so only the",
        "first run pays for the download.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
