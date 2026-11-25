import importlib.util
import sys
from pathlib import Path

import pytest

from paper_radar.stopping import (
    advise, format_advice, knee_ratio, reading_order, simulate, simulate_target,
    stop_consecutive, stop_knee, stop_threshold,
)

ROOT = Path(__file__).resolve().parents[1]


def test_reading_order_is_score_then_id():
    assert reading_order({"b": 0.5, "a": 0.5, "c": 0.9}) == ["c", "a", "b"]


def test_threshold_reads_everything_at_or_above():
    scores = [0.9, 0.5, 0.3, 0.1]
    labels = [True, False, True, False]
    out = simulate(scores, labels, lambda s, r: stop_threshold(s, r, 0.3))
    assert (out.read, out.found, out.recall) == (3, 2, 1.0)
    assert out.wss == pytest.approx(0.25)


def test_consecutive_waits_for_a_dry_run():
    scores = [1 - i / 100 for i in range(100)]
    labels = [i in (0, 15, 30) for i in range(100)]
    out = simulate(scores, labels, lambda s, r: stop_consecutive(s, r, k=20))
    assert out.read == 51 and out.found == 3          # hit at 30, then 20 dry


def test_consecutive_run_grows_with_depth():
    read = [False] * 10 + [True] + [False] * 49
    assert stop_consecutive([0.5] * 1000, read, k=20)
    assert not stop_consecutive([0.5] * 1000, read, k=20, frac=0.9)


def test_floor_blocks_stopping_above_it():
    scores = [0.9] * 30 + [0.1] * 30
    read = [False] * 25
    assert stop_consecutive(scores, read, k=20)
    assert not stop_consecutive(scores, read, k=20, floor=0.5)


def test_knee_ratio_and_stop():
    read = [True] * 50 + [False] * 2000
    ratio, knee = knee_ratio(read)
    assert knee == 50 and ratio == pytest.approx(2000)
    assert stop_knee([0.5] * 3000, read)
    assert not stop_knee([0.5] * 3000, [True, False] * 100)


def test_target_reads_sample_and_prefix():
    labels = [True] * 20 + [False] * 180
    out = simulate_target(labels, t=5, seed=1)
    assert out.found >= 5 and out.read <= 200


def test_target_with_too_few_eligible_reads_everything():
    out = simulate_target([True, False, False], t=10)
    assert out.read == 3 and out.recall == 1.0


def test_advise_counts_only_the_unbroken_prefix():
    scores = {f"p{i}": 1 - i / 100 for i in range(100)}
    labels = {"p0": True, "p1": False, "p5": True}
    advice = advise(scores, labels, k=20, frac=0.0, size_frac=0.0, batch=3)
    assert (advice.read, advice.found, advice.stop) == (2, 1, False)
    assert advice.skipped == ["p5"]
    assert advice.next_ids == ["p2", "p3", "p4"]
    text = format_advice(advice)
    assert "Keep reading" in text and "out of order" in text


def test_advise_stops_after_dry_run():
    scores = {f"p{i}": 1 - i / 100 for i in range(100)}
    labels = {f"p{i}": i == 0 for i in range(60)}
    advice = advise(scores, labels, k=50, frac=0.0, size_frac=0.0)
    assert advice.stop and advice.next_ids == []
    assert "You can stop" in format_advice(advice)


def test_advise_rejects_target():
    with pytest.raises(ValueError):
        advise({"a": 1.0}, {}, rule="target")


def _load_bench():
    here = ROOT / "benchmarks" / "clef_tar_2019"
    sys.path.insert(0, str(here))
    for name in ("loto", "stopping_bench"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("stopping_bench", here / "stopping.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stopping_bench"] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, topic: str, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["topic,pmid,label,verdict,eligibility,triggered"]
    lines += [f"{topic},{i},{int(lab)},include,{score},"
              for i, (score, lab) in enumerate(rows)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_benchmark_script_end_to_end(tmp_path):
    bench = _load_bench()
    for split, topics in (("dev", ("A", "B")), ("test", ("C",))):
        for t in topics:
            rows = [(round(1 - i / 400, 4), i % 40 == 0 and i < 200) for i in range(400)]
            _write(tmp_path / split / f"{t}.csv", t, rows)
    out = tmp_path / "out.md"
    assert bench.main([str(tmp_path / "dev"), str(tmp_path / "test"), "--fit-on", str(tmp_path / "dev"),
                       "--out", str(out)]) == 0
    text = out.read_text()
    assert "fixed threshold" in text and "chosen on dev" in text and "`C`" in text


def test_size_frac_scales_with_review():
    read = [True] + [False] * 120
    assert stop_consecutive([0.5] * 1000, read, k=100)
    assert not stop_consecutive([0.5] * 10000, read, k=100, size_frac=0.03)   # needs 300


def test_cli_progress(tmp_path, monkeypatch, capsys):
    from paper_radar import cli
    from paper_radar.store import Store

    class Cfg:
        data_path = tmp_path

        class screening:
            enabled = True
    store = Store(tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda path: Cfg)
    monkeypatch.setattr(cli, "lint", lambda config: [])
    monkeypatch.setattr(Store, "ranking_index", lambda self: ({"a": 0.9, "b": 0.5, "c": 0.1}, ["m"]))
    store.add_label("a", True, "2026-11-25")
    assert cli.main(["screen", "-c", "x.toml", "--progress"]) == 0
    out = capsys.readouterr().out
    assert "Read in ranked order" in out and "no abstract: 1" in out and "    b" in out


def test_ensemble_averages_scores(tmp_path):
    here = ROOT / "benchmarks" / "clef_tar_2019"
    sys.path.insert(0, str(here))
    spec = importlib.util.spec_from_file_location("ensemble_bench", here / "ensemble.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ensemble_bench"] = module
    spec.loader.exec_module(module)
    _write(tmp_path / "a" / "T.csv", "T", [(0.2, True), (0.8, False)])
    _write(tmp_path / "b" / "T.csv", "T", [(0.6, True), (0.0, False)])
    (tmp_path / "b" / "T.csv").write_text(
        (tmp_path / "b" / "T.csv").read_text().replace("T,1,0,include,0.0,", "T,1,0,manual,0.0,"))
    assert module.main([str(tmp_path / "a"), str(tmp_path / "b"), "--out", str(tmp_path / "o")]) == 0
    rows = (tmp_path / "o" / "T.csv").read_text().splitlines()
    assert rows[1] == "T,0,1,include,0.4000,"
    assert rows[2] == "T,1,0,manual,1.0000,"
