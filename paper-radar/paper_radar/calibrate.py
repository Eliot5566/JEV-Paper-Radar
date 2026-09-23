"""Check Jev's calibration against *your* judgement and fit thresholds to it.

TypeSafe's accuracy and calibration numbers are self-reported. This command lets every user
measure them on their own labels: Brier score, expected calibration error, and a
precision/recall table that suggests `must_read` and `maybe` thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Row:
    threshold: float
    flagged: int
    precision: float
    recall: float


@dataclass
class Report:
    n: int
    positives: int
    brier: float
    ece: float
    rows: list[Row]
    suggested_must_read: float | None
    suggested_maybe: float | None
    warnings: list[str]


def _grid() -> list[float]:
    return [round(0.05 * i, 2) for i in range(1, 20)]


def calibrate(
    relevance: dict[str, float],
    labels: dict[str, bool],
    *,
    target_precision: float = 0.9,
    target_recall: float = 0.9,
    bins: int = 10,
) -> Report:
    pairs = [(relevance[k], 1 if v else 0) for k, v in labels.items() if k in relevance]
    warnings: list[str] = []
    missing = len(labels) - len(pairs)
    if missing:
        warnings.append(f"{missing} labelled paper(s) have no stored decision and were ignored.")
    n = len(pairs)
    positives = sum(y for _, y in pairs)
    if n < 30 or positives < 5:
        warnings.append("Fewer than 30 labels or 5 relevant papers: treat these numbers as a rough first look.")
    if n == 0:
        return Report(0, 0, float("nan"), float("nan"), [], None, None, warnings)

    brier = sum((p - y) ** 2 for p, y in pairs) / n
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [(p, y) for p, y in pairs if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        if bucket:
            confidence = sum(p for p, _ in bucket) / len(bucket)
            accuracy = sum(y for _, y in bucket) / len(bucket)
            ece += len(bucket) / n * abs(confidence - accuracy)

    rows: list[Row] = []
    for t in _grid():
        flagged = [(p, y) for p, y in pairs if p >= t]
        tp = sum(y for _, y in flagged)
        precision = tp / len(flagged) if flagged else 1.0
        recall = tp / positives if positives else 0.0
        rows.append(Row(t, len(flagged), precision, recall))

    must = next((r.threshold for r in rows if r.flagged and r.precision >= target_precision), None)
    maybe = next((r.threshold for r in reversed(rows) if r.recall >= target_recall), None)
    return Report(n, positives, brier, ece, rows, must, maybe, warnings)


def format_report(report: Report, target_precision: float, target_recall: float) -> str:
    out = [f"Labelled papers: {report.n} ({report.positives} relevant)"]
    if report.n:
        out.append(f"Brier score: {report.brier:.3f}   (0 is perfect; 0.25 is a coin flip)")
        out.append(f"Expected calibration error: {report.ece:.3f}   (lower is better; < 0.05 is well calibrated)")
        out.append("")
        out.append(" thresh  flagged  precision  recall")
        for r in report.rows:
            out.append(f"  {r.threshold:>4.2f}  {r.flagged:>7}  {r.precision:>9.2f}  {r.recall:>6.2f}")
        out.append("")
        out.append(
            f"Suggested must_read (precision >= {target_precision:.0%}): "
            + (f"{report.suggested_must_read:.2f}" if report.suggested_must_read is not None else "not reachable")
        )
        out.append(
            f"Suggested maybe (recall >= {target_recall:.0%}): "
            + (f"{report.suggested_maybe:.2f}" if report.suggested_maybe is not None else "not reachable")
        )
    out.extend(f"note: {w}" for w in report.warnings)
    return "\n".join(out)
