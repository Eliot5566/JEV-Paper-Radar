from pathlib import Path

from paper_radar.cli import _normalize_id, main
from paper_radar.store import Store

ROOT = Path(__file__).resolve().parents[1]


def test_normalize_id():
    assert _normalize_id("2609.01234") == "arxiv:2609.01234"
    assert _normalize_id("2609.01234v2") == "arxiv:2609.01234"
    assert _normalize_id("https://arxiv.org/abs/2609.01234v1") == "arxiv:2609.01234"
    assert _normalize_id("https://arxiv.org/pdf/2609.01234.pdf") == "arxiv:2609.01234"
    assert _normalize_id("arxiv:2609.01234") == "arxiv:2609.01234"
    assert _normalize_id("biorxiv:10.1101/2026.09.20.123") == "biorxiv:10.1101/2026.09.20.123"


def test_demo_label_calibrate(tmp_path, capsys):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out), "--date", "2026-09-22"]) == 0
    assert (out / "site" / "index.html").exists()
    cfg = str(out / "radar.demo.toml")
    assert main(["label", "2609.99001", "yes", "-c", cfg]) == 0
    assert main(["label", "2609.99007", "no", "-c", cfg]) == 0
    assert Store(out / "data").load_labels() == {"arxiv:2609.99001": True, "arxiv:2609.99007": False}
    assert main(["calibrate", "-c", cfg]) == 0
    assert "Labelled papers: 2" in capsys.readouterr().out
    assert main(["demo", "--out", str(out), "--date", "2026-09-22"]) == 0  # re-running resets cleanly


def test_check(capsys):
    assert main(["check", "-c", str(ROOT / "radar.toml")]) == 0
    out = capsys.readouterr().out
    assert "Config OK" in out and "papers/day" in out


def test_missing_key_exit_code(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    cfg = tmp_path / "radar.toml"
    cfg.write_text('[[sources]]\ntype = "arxiv"\n[[interests]]\nid = "a"\ntext = "x"\n')
    assert main(["run", "-c", str(cfg)]) == 2
    assert "TYPESAFE_API_KEY is not set" in capsys.readouterr().err


def test_bad_config_exit_code(tmp_path, capsys):
    cfg = tmp_path / "radar.toml"
    cfg.write_text("[radar]\ntitel = 'x'\n")
    assert main(["check", "-c", str(cfg)]) == 2
    assert "Unknown key" in capsys.readouterr().err
