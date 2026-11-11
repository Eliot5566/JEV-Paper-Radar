"""`__version__` must track the version in pyproject.toml.

Regression test for the 0.1.1-0.1.3 releases shipping with
`__version__` still hardcoded to "0.1.0", so `paper-radar --version`
printed 0.1.0 while pip reported 0.1.3.
"""

import tomllib
from pathlib import Path

from paper_radar import __version__


def test_version_matches_pyproject():
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert __version__ == pyproject["project"]["version"]
