"""The installed CLI must finish under a legacy Windows pipe encoding."""

import os
import subprocess
import sys
from pathlib import Path


def test_demo_finishes_with_cp950_output(tmp_path):
    env = dict(os.environ, PYTHONIOENCODING="cp950:strict",
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [sys.executable, "-m", "paper_radar", "demo", "--out", str(tmp_path / "demo"), "--date", "2026-11-13"],
        env=env, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode("cp950", errors="replace")
    assert (tmp_path / "demo" / "site" / "index.html").is_file()
    assert "Done:" in result.stdout.decode("cp950")
