"""Title/abstract screening for systematic reviews.

What this is, and what it is not. Published evaluations of automated screening report
a mean recall around 93% and a mean workload saving of about 55% at 95% recall, and
they consistently conclude that automation belongs *alongside* human screeners rather
than in place of one. So this module is built as a second screener: it never produces
a final exclusion on its own, it reports the numbers PRISMA 2020 asks for, and every
threshold it suggests is fitted to a recall target the reviewer sets, not to accuracy.

Three deliberate choices follow from that:

* **Conjunction across every criterion, not just the weakest.** A record is eligible
  only if all include criteria hold. The obvious way to score that is `min(p)` — and it
  was the original default here until a benchmark showed what it costs. `min` throws
  away everything except one number, so two records whose worst criterion scores 0.02
  rank identically even when one matches the other criteria at 0.95 and the other at
  0.10. The default is now the geometric mean of the criteria, which keeps the
  conjunction (any criterion near zero still sinks the record) while letting the rest of
  the evidence break the ties `min` collapses. `combine = "min"` restores the old
  behaviour. See `benchmarks/clef_tar_2019/`.
* **No abstract means manual review, never exclusion.** PubMed is full of records with
  a title and nothing else. Judging those on a title would produce confident nonsense.
* **The threshold errs toward reading.** Missing an eligible study is the expensive
  error in a review; reading one extra abstract costs a minute.

One consequence worth stating for anyone writing criteria: under a conjunction, every
criterion you add is another chance to veto a record. That is the opposite of the daily
radar, where relevance is a max over interests and adding one can only help.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import Config
from .models import JevResult, Paper
from .questions import SCREEN_EXCLUDE_PREFIX, SCREEN_INCLUDE_PREFIX

# The verdict a record gets. "manual" is not a failure mode — it is the honest answer
# when there is nothing to judge.
INCLUDE = "include"
EXCLUDE = "exclude"
EXCLUDE_CRITERION = "exclude_criterion"
MANUAL = "manual"
VERDICTS = (INCLUDE, EXCLUDE, EXCLUDE_CRITERION, MANUAL)


@dataclass
class ScreenDecision:
    paper: Paper
    verdict: str
    eligibility: float                      # min over include criteria
    include: dict[str, float] = field(default_factory=dict)
    exclude: dict[str, float] = field(default_factory=dict)
    weakest: str = ""                       # which include criterion held it back
    triggered: list[str] = field(default_factory=list)  # exclude criteria that fired
    model: str = ""
    input_tokens: int = 0
    cost: float = 0.0

    @property
    def screened(self) -> bool:
        """False when the record could not be judged and a human has to look."""
        return self.verdict != MANUAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper": {k: getattr(self.paper, k) for k in ("id", "source", "title", "url")},
            "verdict": self.verdict,
            "eligibility": round(self.eligibility, 4),
            "include": {k: round(v, 4) for k, v in self.include.items()},
            "exclude": {k: round(v, 4) for k, v in self.exclude.items()},
            "weakest": self.weakest,
            "triggered": self.triggered,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "cost": self.cost,
        }


def combine_criteria(values: list[float], mode: str = "geometric") -> float:
    """Turn one probability per criterion into one eligibility score.

    `geometric` is the geometric mean: the product, which is the conjunction under
    independence, rescaled to stay on a 0-1 scale so a threshold means the same thing
    whether a review has three criteria or six. Within one review the rescaling does not
    change the ranking, so this is simply "use all the evidence" instead of "use the
    worst number and discard the rest".

    `min` is the strict weakest-link reading. It is kept because it is the honest
    interpretation of a conjunction when a low score really does mean "this criterion is
    false" — but on abstracts a low score usually means "the abstract does not say",
    which is not the same thing.
    """
    if not values:
        return 0.0
    if mode == "min":
        return min(values)
    return math.prod(values) ** (1 / len(values))


def screen(paper: Paper, result: JevResult, config: Config) -> ScreenDecision:
    settings = config.screening
    answers = result.answers
    include = {c.id: float(answers[SCREEN_INCLUDE_PREFIX + c.id]["noul"]) for c in settings.include}
    exclude = {c.id: float(answers[SCREEN_EXCLUDE_PREFIX + c.id]["noul"]) for c in settings.exclude}

    weakest_id = min(include, key=lambda k: include[k]) if include else ""
    eligibility = combine_criteria(list(include.values()), settings.combine)
    triggered = sorted(k for k, v in exclude.items() if v >= settings.exclude_threshold)

    if not paper.abstract.strip():
        verdict = MANUAL
    elif triggered:
        verdict = EXCLUDE_CRITERION
    elif eligibility >= settings.threshold:
        verdict = INCLUDE
    else:
        verdict = EXCLUDE

    cost = result.cost if result.cost is not None else result.input_tokens * config.jev.price_per_mtok / 1_000_000
    return ScreenDecision(
        paper=paper,
        verdict=verdict,
        eligibility=eligibility,
        include=include,
        exclude=exclude,
        weakest=weakest_id,
        triggered=triggered,
        model=result.model,
        input_tokens=result.input_tokens,
        cost=cost,
    )


# ── PRISMA 2020 reporting ────────────────────────────────────────────────────────

def prisma_counts(decisions: Iterable[ScreenDecision], *, identified: int, duplicates: int = 0) -> dict[str, Any]:
    """The counts PRISMA 2020's flow diagram asks for at the title/abstract stage.

    The 2020 diagram has a box for records removed before screening by "automation
    tool exclusions" — that is the line this tool is entitled to fill in, and only
    when a human has agreed to act on it. It is reported separately from records a
    person excluded, because conflating the two is exactly what reviewers object to.
    """
    decisions = list(decisions)
    by_verdict = {verdict: sum(1 for d in decisions if d.verdict == verdict) for verdict in VERDICTS}
    reasons: dict[str, int] = {}
    for decision in decisions:
        for criterion in decision.triggered:
            reasons[criterion] = reasons.get(criterion, 0) + 1
    return {
        "identified": identified,
        "duplicates_removed": duplicates,
        "screened": len(decisions),
        "automation_excluded": by_verdict[EXCLUDE] + by_verdict[EXCLUDE_CRITERION],
        "excluded_by_criterion": by_verdict[EXCLUDE_CRITERION],
        "excluded_low_eligibility": by_verdict[EXCLUDE],
        "exclusion_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "sought_for_retrieval": by_verdict[INCLUDE],
        "manual_review": by_verdict[MANUAL],
    }


def format_prisma(counts: dict[str, Any]) -> str:
    lines = [
        "PRISMA 2020 — identification and screening",
        "",
        f"  Records identified                      {counts['identified']:>6}",
        f"  Duplicate records removed               {counts['duplicates_removed']:>6}",
        f"  Records screened                        {counts['screened']:>6}",
        f"  Records marked ineligible by this tool  {counts['automation_excluded']:>6}",
        f"      by an exclusion criterion           {counts['excluded_by_criterion']:>6}",
        f"      below the eligibility threshold     {counts['excluded_low_eligibility']:>6}",
        f"  Reports sought for retrieval            {counts['sought_for_retrieval']:>6}",
        f"  Needs manual review (no abstract)       {counts['manual_review']:>6}",
    ]
    if counts["exclusion_reasons"]:
        lines += ["", "  Exclusion criteria that fired:"]
        lines += [f"      {name:<34}{n:>6}" for name, n in counts["exclusion_reasons"].items()]
    lines += [
        "",
        "  These are automation counts, not a completed screen. PRISMA 2020 expects",
        "  automation-tool exclusions to be reported separately from human decisions.",
    ]
    return "\n".join(lines)


# ── Measuring it against a human screener ───────────────────────────────────────

@dataclass
class ScreenPerformance:
    n: int
    positives: int
    threshold: float
    recall: float
    precision: float
    workload_saved: float       # WSS at the achieved recall
    missed: list[str]
    target_recall: float
    warnings: list[str] = field(default_factory=list)


def screening_performance(
    eligibility: dict[str, float], labels: dict[str, bool], *, target_recall: float = 0.95
) -> ScreenPerformance:
    """Fit the threshold that reaches `target_recall` on a human-screened sample.

    Reports WSS — Work Saved over Sampling — the metric this literature uses:
    WSS@R = (TN + FN) / N − (1 − R). It answers the only question a review team
    actually has: how much of the pile can I not read, and what does that cost me?
    """
    pairs = [(eligibility[pid], labels[pid]) for pid in labels if pid in eligibility]
    warnings: list[str] = []
    missing = len(labels) - len(pairs)
    if missing:
        warnings.append(f"{missing} labelled record(s) have no stored decision and were ignored.")
    if not pairs:
        return ScreenPerformance(0, 0, 0.0, 0.0, 0.0, 0.0, [], target_recall,
                                 warnings + ["No labelled records overlap the screening output."])
    positives = sum(1 for _, keep in pairs if keep)
    if positives == 0:
        return ScreenPerformance(len(pairs), 0, 0.0, 0.0, 0.0, 0.0, [], target_recall,
                                 warnings + ["No eligible studies in the labelled sample; nothing to fit."])
    if positives < 10:
        warnings.append(f"Only {positives} eligible studies labelled. Any threshold fitted here is rough.")

    # The highest threshold that still keeps the target share of eligible studies.
    # Candidates are the scores themselves, so the fit lands exactly on a record.
    needed = -(-positives * target_recall // 1)  # ceil
    kept = sorted((score for score, keep in pairs if keep), reverse=True)
    threshold = kept[int(needed) - 1] if int(needed) <= len(kept) else kept[-1]

    tp = sum(1 for score, keep in pairs if keep and score >= threshold)
    fp = sum(1 for score, keep in pairs if not keep and score >= threshold)
    tn = sum(1 for score, keep in pairs if not keep and score < threshold)
    fn = positives - tp
    n = len(pairs)
    recall = tp / positives
    precision = tp / (tp + fp) if tp + fp else 0.0
    missed = sorted(pid for pid in labels if labels[pid] and eligibility.get(pid, 1.0) < threshold)
    return ScreenPerformance(
        n=n,
        positives=positives,
        threshold=threshold,
        recall=recall,
        precision=precision,
        workload_saved=(tn + fn) / n - (1 - recall),
        missed=missed,
        target_recall=target_recall,
        warnings=warnings,
    )


def format_performance(report: ScreenPerformance) -> str:
    if not report.n:
        return "\n".join(["Screening performance", ""] + [f"  ! {w}" for w in report.warnings])
    to_read = round(report.n * (1 - report.workload_saved - (1 - report.recall)))
    lines = [
        "Screening performance against your own decisions",
        "",
        f"  Labelled records                {report.n:>8}",
        f"  Eligible among them             {report.positives:>8}",
        f"  Target recall                   {report.target_recall:>8.0%}",
        "",
        f"  Suggested threshold             {report.threshold:>8.3f}",
        f"  Recall at that threshold        {report.recall:>8.1%}",
        f"  Precision at that threshold     {report.precision:>8.1%}",
        f"  Workload saved (WSS)            {report.workload_saved:>8.1%}",
        "",
        f"  You would read about {to_read} of {report.n} abstracts and miss "
        f"{len(report.missed)} of {report.positives} eligible studies.",
    ]
    if report.missed:
        shown = ", ".join(report.missed[:5])
        more = f" (+{len(report.missed) - 5} more)" if len(report.missed) > 5 else ""
        lines += ["", f"  Missed: {shown}{more}",
                  "  Read these before trusting the threshold — they are what it costs you."]
    lines += [f"  ! {w}" for w in report.warnings]
    return "\n".join(lines)
