"""benchmarks/clef_tar_2019/loto.py on small synthetic dumps (no model, no network)."""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("loto", ROOT / "benchmarks" / "clef_tar_2019" / "loto.py")
loto = importlib.util.module_from_spec(spec)
sys.modules["loto"] = loto  # dataclasses look their module up here
spec.loader.exec_module(loto)

HEADER = ["topic", "pmid", "label", "verdict", "eligibility", "weakest", "triggered", "design"]


def _dump(directory: Path, topic: str, rows):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{topic}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for i, (label, verdict, score, triggered) in enumerate(rows):
            writer.writerow([topic, f"{topic}{i}", label, verdict, score, "design", triggered, score])


def _topic(eligible_scores, n_negative=20, negative_score=0.05):
    rows = [(1, "include", s, "") for s in eligible_scores]
    rows += [(0, "exclude", negative_score, "") for _ in range(n_negative)]
    return rows


def test_triggered_scores_zero_and_manual_scores_one(tmp_path):
    _dump(tmp_path, "T1", [(1, "exclude", 0.9, "animal"), (1, "manual", 0.0, ""), (0, "include", 0.7, "")])
    records = loto.load_dump(tmp_path / "T1.csv", [])
    assert [r.score for r in records] == [0.0, 1.0, 0.7]
    assert [r.judged for r in records] == [True, False, True]


def test_old_dump_without_triggered_warns(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text("topic,pmid,label,verdict,eligibility,weakest,design\nT,1,1,include,0.9,design,0.9\n")
    warnings = []
    loto.load_dump(path, warnings)
    assert warnings and "triggered" in warnings[0]


def test_leave_one_out_uses_other_topics_only(tmp_path):
    # Topic A's eligible studies score high, B's score low. B's own threshold is
    # low; scored with A's threshold, B loses recall: that is what LOTO exposes.
    _dump(tmp_path, "A", _topic([0.9] * 20))
    _dump(tmp_path, "B", _topic([0.2] * 20))
    topics = loto.load_dir(tmp_path, [])
    result = loto.analyse(topics, None, 0.95)
    own = {t: m for t, _, m in result["in_sample"]}
    pooled = {t: (thr, m) for t, thr, m in result["modes"]["pooled"]}
    assert own["B"]["recall"] == 1.0
    assert pooled["B"][0] == pytest.approx(0.9)  # fitted on A alone
    assert pooled["B"][1]["recall"] == 0.0


def test_fit_on_tests_only_the_other_topics(tmp_path):
    _dump(tmp_path / "dev", "D1", _topic([0.6] * 10))
    _dump(tmp_path / "dev", "D2", _topic([0.4] * 10))
    _dump(tmp_path / "hold", "H1", _topic([0.5] * 10))
    out = tmp_path / "report.md"
    code = loto.main([str(tmp_path / "dev"), str(tmp_path / "hold"), "--fit-on", str(tmp_path / "dev"),
                      "--out", str(out)])
    text = out.read_text()
    assert code == 0 and "`H1`" in text and "`D1`" not in text
    # min of the dev thresholds is 0.4, which keeps every H1 eligible study.
    assert "| 0.400 | 100.0% |" in text


def test_wilson_interval():
    lo, hi = loto.wilson(123, 127)
    assert lo == pytest.approx(0.9218, abs=1e-3) and hi == pytest.approx(0.9877, abs=1e-3)


def test_run_topic_mock_dump_has_triggered_and_cost(tmp_path):
    spec_run = importlib.util.spec_from_file_location("clef_run", ROOT / "benchmarks" / "clef_tar_2019" / "run.py")
    run = importlib.util.module_from_spec(spec_run)
    sys.modules["clef_run"] = run
    spec_run.loader.exec_module(run)
    from paper_radar.config import JevSettings
    from paper_radar.jev import make_backend

    topic_file = sorted((ROOT / "benchmarks" / "clef_tar_2019" / "criteria" / "holdout").glob("*.toml"))[0]
    judged = {"1": 1, "2": 0, "3": 0}
    records = {"1": {"title": "A randomised trial", "abstract": "Patients were randomised."},
               "2": {"title": "A rat study", "abstract": "Rats."},
               "3": {"title": "No abstract here", "abstract": ""}}
    result = run.run_topic(topic_file, judged, records, make_backend(JevSettings(backend="mock")), 0.95,
                           log=lambda m: None, dump=tmp_path)
    assert result["cost"] == 0.0 and result["cost_complete"] is True
    header = next(csv.reader((tmp_path / f"{result['topic']}.csv").open(encoding="utf-8")))
    assert "triggered" in header
    rows = loto.load_dump(tmp_path / f"{result['topic']}.csv", [])
    assert len(rows) == 3 and sum(not r.judged for r in rows) == 1
