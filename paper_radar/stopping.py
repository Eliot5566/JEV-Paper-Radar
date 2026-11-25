"""When can a reviewer stop reading? Stopping rules for ranked screening.

The benchmark showed what a fixed threshold costs. Fitted on other reviews, one cut-off
has to be low enough for the hardest review, so on a typical review it keeps far more
records than needed (CLEF TAR 2019: 99.2% recall but 44% work saved, against 78% when
the threshold is tuned on the review's own answers). The best cut-off ranges from 0.11
to 0.87 between reviews, so no single number fixes that.

The way out is to use the labels a reviewer produces anyway. Screening with this tool
means reading records in order of eligibility, highest first, and recording each
decision (`paper-radar label`). Those decisions are labels for *this* review, and they
arrive for free. A stopping rule looks at them and says when reading further is very
unlikely to find another eligible study.

Rules provided, all measured in `benchmarks/clef_tar_2019/stopping.py`:

* ``threshold``: read everything scoring at or above a fixed cut-off (the baseline).
* ``consecutive``: stop after ``k`` irrelevant records in a row, but never before
  every record above ``floor`` has been read. Simple to explain, and the floor keeps
  it from stopping in a dry patch near the top.
* ``knee``: Cormack & Grossman's knee method (2016, adjusted form): stop when the
  rate of finding eligible studies has fallen far below the early rate.
* ``target``: Cormack & Grossman's target method. Read a random sample until ``t``
  eligible studies are found, then read in rank order until each of them is reached.
  The only rule here with a statistical guarantee, and the most reading.

No rule produces a final exclusion: what is left unread is what a reviewer chooses not
to read, with the numbers in front of them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Sequence

RULES = ("threshold", "consecutive", "knee", "target")

# Defaults for live advice, chosen on the eight CLEF TAR development reviews only and
# reported on the four held-out ones (benchmarks/clef_tar_2019/results.stopping.*.md).
STOP_DEFAULT_K = 50
STOP_DEFAULT_FRAC = 0.2
STOP_DEFAULT_THRESHOLD = 0.235


def reading_order(scores: dict[str, float]) -> list[str]:
    """Highest score first; ties broken by id so the order is reproducible."""
    return sorted(scores, key=lambda pid: (-scores[pid], pid))


# ----------------------------------------------------------------------------- rules
# Each rule sees the scores in reading order and the labels of the records read so far
# (a prefix of that order) and answers: stop now?


def stop_threshold(scores: Sequence[float], read: Sequence[bool], threshold: float) -> bool:
    return len(read) >= len(scores) or scores[len(read)] < threshold


def stop_consecutive(scores: Sequence[float], read: Sequence[bool], k: int, floor: float = 1.01,
                     frac: float = 0.0, size_frac: float = 0.0) -> bool:
    """Stop after a dry run of max(k, frac * records read so far) irrelevant records.

    `frac` makes the run grow with depth: 20 dry records mean little after reading
    2,000, a lot after reading 60. `size_frac` makes it grow with the review instead:
    the run is at least that share of all ranked records. `floor` forbids stopping
    while anything scoring at or above it is unread.
    """
    n = len(read)
    if n >= len(scores):
        return True
    if scores[n] >= floor:
        return False
    run = max(k, int(frac * n), int(size_frac * len(scores)))
    if n < run:
        return False
    return not any(read[n - run:])


def knee_ratio(read: Sequence[bool]) -> tuple[float, int]:
    """Slope ratio at the knee of the gain curve, and where the knee is.

    The knee is the point of the cumulative-found curve farthest from the straight line
    joining its ends. The ratio compares the finding rate before it with the rate after
    it (+1 smoothing, as in the paper), so a long dry run after the knee drives it up.
    """
    s = len(read)
    found = 0
    curve = []
    for flag in read:
        found += flag
        curve.append(found)
    total = curve[-1] if curve else 0
    if s == 0 or total == 0:
        return 0.0, 0
    best_i, best_d = 1, -1.0
    for i in range(1, s + 1):
        # distance from (i, curve[i-1]) to the line (0,0)-(s,total), up to a constant
        d = curve[i - 1] * s - i * total
        if d > best_d:
            best_d, best_i = d, i
    before = curve[best_i - 1] / best_i
    after = (total - curve[best_i - 1] + 1) / max(1, s - best_i)
    return before / after, best_i


def stop_knee(scores: Sequence[float], read: Sequence[bool], min_read: int = 150, every: int = 1) -> bool:
    s = len(read)
    if s >= len(scores):
        return True
    if s < min_read or (s % every):
        return False
    found = sum(read)
    ratio, _ = knee_ratio(read)
    return ratio >= 156 - min(found, 150)


@dataclass
class Outcome:
    read: int
    found: int
    total: int
    eligible: int

    @property
    def recall(self) -> float:
        return self.found / self.eligible if self.eligible else float("nan")

    @property
    def wss(self) -> float:
        if not self.total or not self.eligible:
            return float("nan")
        return (self.total - self.read) / self.total - (1 - self.recall)


def simulate(scores: Sequence[float], labels: Sequence[bool],
             stop: Callable[[Sequence[float], Sequence[bool]], bool]) -> Outcome:
    """Read in order (scores must already be sorted high to low) until `stop` says so."""
    read: list[bool] = []
    while not stop(scores, read):
        read.append(labels[len(read)])
    return Outcome(len(read), sum(read), len(scores), sum(labels))


def simulate_target(labels: Sequence[bool], t: int = 10, seed: int = 0) -> Outcome:
    """Target method. Records read = the random sample plus the ranked prefix."""
    rng = random.Random(seed)
    idx = list(range(len(labels)))
    rng.shuffle(idx)
    sample, hits = set(), []
    for i in idx:
        sample.add(i)
        if labels[i]:
            hits.append(i)
            if len(hits) >= t:
                break
    prefix = max(hits) + 1 if hits else len(labels)
    if len(hits) < t:          # fewer eligible studies than the target: read everything
        prefix = len(labels)
    read_set = sample | set(range(prefix))
    found = sum(1 for i in read_set if labels[i])
    return Outcome(len(read_set), found, len(labels), sum(labels))


# ----------------------------------------------------------------------- live advice


@dataclass
class Advice:
    total: int
    read: int                 # top-ranked records read in order (a contiguous prefix)
    found: int
    stop: bool
    rule: str
    reason: str
    next_ids: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # labelled out of order, ignored by the rule


def advise(scores: dict[str, float], labels: dict[str, bool], *, rule: str = "consecutive",
           k: int = STOP_DEFAULT_K, frac: float = STOP_DEFAULT_FRAC, floor: float = 1.01,
           threshold: float = STOP_DEFAULT_THRESHOLD, batch: int = 20) -> Advice:
    """What to do next on a review that is being read in ranked order."""
    if rule not in ("threshold", "consecutive", "knee"):
        raise ValueError(f"rule must be threshold, consecutive or knee for live advice, not {rule!r}")
    order = reading_order(scores)
    ordered_scores = [scores[pid] for pid in order]
    read: list[bool] = []
    for pid in order:
        if pid not in labels:
            break
        read.append(labels[pid])
    skipped = [pid for pid in order[len(read):] if pid in labels]
    if rule == "threshold":
        stop = stop_threshold(ordered_scores, read, threshold)
        reason = f"every record scoring {threshold:.3f} or more has been read" if stop else \
            f"records scoring {threshold:.3f} or more are still unread"
    elif rule == "consecutive":
        stop = stop_consecutive(ordered_scores, read, k, floor, frac)
        n = len(read)
        run_needed = max(k, int(frac * n))
        if stop and n < len(order):
            reason = f"the last {run_needed} records read were all irrelevant"
        elif stop:
            reason = "every record has been read"
        elif n < len(order) and ordered_scores[n] >= floor:
            reason = f"records scoring {floor:.3f} or more are still unread"
        else:
            run = next((i for i, flag in enumerate(reversed(read)) if flag), len(read))
            reason = f"{run} irrelevant in a row so far; the rule waits for {run_needed}"
    else:
        stop = stop_knee(ordered_scores, read)
        ratio, _ = knee_ratio(read)
        need = 156 - min(sum(read), 150)
        reason = f"knee slope ratio {ratio:.1f}, needs {need}" + ("" if len(read) >= 150 else "; and at least 150 read")
    next_ids = [] if stop else [pid for pid in order[len(read):] if pid not in labels][:batch]
    return Advice(len(order), len(read), sum(read), stop, rule, reason, next_ids, skipped)


def format_advice(advice: Advice) -> str:
    lines = [
        f"Screening progress ({advice.rule} rule)",
        f"  Records ranked                  {advice.total:>8,}",
        f"  Read in ranked order            {advice.read:>8,}",
        f"  Eligible found so far           {advice.found:>8,}",
        f"  Left unread if you stop now     {advice.total - advice.read:>8,}",
        "",
        ("  You can stop: " if advice.stop else "  Keep reading: ") + advice.reason + ".",
    ]
    if advice.skipped:
        lines.append(f"  ({len(advice.skipped)} records were labelled out of order; the rule counts only "
                     "the unbroken run from the top.)")
    if advice.next_ids:
        lines += ["", f"  Next {len(advice.next_ids)} to read, highest score first:"]
        lines += [f"    {pid}" for pid in advice.next_ids]
    return "\n".join(lines)
