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


def test_dotenv_is_loaded_but_never_overrides_real_env(tmp_path, monkeypatch):
    from paper_radar.cli import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text('TYPESAFE_API_KEY="from-dotenv"\n# comment\n\nEMPTY\nOTHER=plain\n', encoding="utf-8")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("OTHER", "from-shell")
    loaded = load_dotenv(env_file)
    assert loaded == ["TYPESAFE_API_KEY"]
    import os

    assert os.environ["TYPESAFE_API_KEY"] == "from-dotenv"
    assert os.environ["OTHER"] == "from-shell"
    assert load_dotenv(tmp_path / "missing.env") == []


def test_run_reads_key_from_dotenv_next_to_config(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("TYPESAFE_API_KEY=k-from-dotenv\n", encoding="utf-8")
    cfg = tmp_path / "radar.toml"
    feed = ROOT / "paper_radar" / "demo" / "arxiv_demo.xml"  # local file: the test never hits the network
    cfg.write_text(
        f'[jev]\nbackend = "typesafe"\n[[sources]]\ntype = "arxiv"\nfile = "{feed.as_posix()}"\n'
        '[[interests]]\nid = "a"\ntext = "x"\n',
        encoding="utf-8",
    )
    main(["run", "-c", str(cfg), "--dry-run"])
    import os

    assert os.environ["TYPESAFE_API_KEY"] == "k-from-dotenv"  # no "key is not set" failure
