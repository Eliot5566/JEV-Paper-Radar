from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from paper_radar.config import parse_config

DEMO_FEED = Path(__file__).resolve().parents[1] / "paper_radar" / "demo" / "arxiv_demo.xml"

# Keys and webhooks the CLI reads from the environment. A test must never pick up
# a real one: `main()` loads .env from the working directory, so without this a
# `pytest` run inside a configured checkout would judge a live day of arXiv on the
# maintainer's account and bill them for it.
LIVE_ENV_VARS = (
    "TYPESAFE_API_KEY",
    "OPENROUTER_API_KEY",
    "LLM_API_KEY",
    "GITHUB_REPOSITORY",
    "GITHUB_TOKEN",
    "SLACK_WEBHOOK_URL",
    "DISCORD_WEBHOOK_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


@pytest.fixture(autouse=True)
def hermetic(tmp_path_factory, monkeypatch):
    """No real credentials, no .env, no outbound network — for every test.

    Tests either inject their own fakes (`fetch=`, `poster=`, `MockBackend`) or
    talk to a throwaway server on loopback, so any request leaving the machine is
    a mistake and should fail loudly rather than quietly cost money.
    """
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
    for name in LIVE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    real_urlopen = urllib.request.urlopen

    def guarded(request, *args, **kwargs):
        url = getattr(request, "full_url", request)
        host = urllib.parse.urlsplit(str(url)).hostname or ""
        if host in ("127.0.0.1", "::1", "localhost"):
            return real_urlopen(request, *args, **kwargs)
        raise AssertionError(f"tests must not reach the network: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", guarded)


def make_config(tmp_path: Path, **overrides):
    raw = {
        "radar": {"title": "Test Radar"},
        "jev": {"backend": "mock"},
        "sources": [{"type": "arxiv", "file": str(DEMO_FEED)}],
        "interests": [
            {"id": "agent_eval", "label": "Agent evaluation", "text": "Benchmarks or methods for evaluating LLM agents on multi-step tool-use tasks"},
            {"id": "calibration", "text": "Calibration or uncertainty estimation of language model predictions"},
        ],
        "exclude": [{"id": "medical_imaging", "text": "The main application is medical imaging such as CT or MRI scans"}],
        "thresholds": {"must_read": 0.8, "maybe": 0.5, "exclude": 0.7},
    }
    raw.update(overrides)
    return parse_config(raw, base_dir=tmp_path)


@pytest.fixture
def config(tmp_path):
    return make_config(tmp_path)
