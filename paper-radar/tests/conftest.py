from __future__ import annotations

from pathlib import Path

import pytest

from paper_radar.config import parse_config

DEMO_FEED = Path(__file__).resolve().parents[1] / "paper_radar" / "demo" / "arxiv_demo.xml"


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
