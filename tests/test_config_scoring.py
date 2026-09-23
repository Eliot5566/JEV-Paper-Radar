import pytest

from paper_radar.config import ConfigError, lint, load_config, parse_config
from paper_radar.models import JevResult, Paper
from paper_radar.questions import build_questions
from paper_radar.scoring import combine, decide

from .conftest import make_config


def test_example_config_is_valid():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "radar.toml")
    assert config.interests and config.sources
    for profile in (root / "profiles").glob("*.toml"):
        load_config(profile)


def test_unknown_keys_are_rejected(tmp_path):
    with pytest.raises(ConfigError, match="Unknown key"):
        make_config(tmp_path, thresholds={"must_read": 0.8, "mabye": 0.5})
    with pytest.raises(ConfigError, match="top-level"):
        make_config(tmp_path, interest=[])


@pytest.mark.parametrize(
    "override, message",
    [
        ({"interests": []}, "at least one"),
        ({"sources": []}, "sources"),
        ({"thresholds": {"must_read": 0.4, "maybe": 0.6}}, "maybe must be <="),
        ({"jev": {"backend": "gpt"}}, "backend"),
        ({"interests": [{"id": "Bad-ID", "text": "x"}]}, "must match"),
        ({"interests": [{"id": "a", "text": "x", "weight": 1.5}]}, "weight"),
        ({"sources": [{"type": "rss"}]}, "needs a url"),
    ],
)
def test_validation_errors(tmp_path, override, message):
    with pytest.raises(ConfigError, match=message):
        make_config(tmp_path, **override)


def test_duplicate_ids(tmp_path):
    with pytest.raises(ConfigError, match="Duplicate"):
        make_config(tmp_path, exclude=[{"id": "agent_eval", "text": "x"}])


def test_lint_flags_negations_and_dates(tmp_path):
    config = make_config(
        tmp_path,
        interests=[
            {"id": "a", "text": "Papers about agents but not robotics"},
            {"id": "b", "text": "Work published after 2024 on retrieval"},
        ],
    )
    warnings = lint(config)
    assert any("negation" in w for w in warnings)
    assert any("dates" in w for w in warnings)


def test_questions_shape(config):
    questions = build_questions(config)
    assert questions["i_agent_eval"] == {
        "type": "noul",
        "instructions": "Benchmarks or methods for evaluating LLM agents on multi-step tool-use tasks",
    }
    assert questions["x_medical_imaging"]["type"] == "noul"
    assert questions["s_paper_type"]["type"] == "choice"
    assert len(questions["s_paper_type"]["criteria"]) <= 255
    assert questions["s_code"]["type"] == "noul"
    assert "s_evidence" not in questions


def test_noul_criteria_passthrough(tmp_path):
    config = make_config(
        tmp_path,
        interests=[{"id": "a", "text": "About agents", "true": "Agents are central", "false": "Agents are mentioned in passing"}],
    )
    q = build_questions(config)["i_a"]
    assert q["criteria"] == {"true": "Agents are central", "false": "Agents are mentioned in passing"}


def _result(config, interest_ps, exclusion_ps, **extra):
    answers = {f"i_{k}": {"type": "noul", "noul": v} for k, v in interest_ps.items()}
    answers.update({f"x_{k}": {"type": "noul", "noul": v} for k, v in exclusion_ps.items()})
    answers["s_paper_type"] = {"type": "choice", "choice": "benchmark", "probabilities": {}, "confidence": 0.8}
    answers["s_code"] = {"type": "noul", "noul": 0.9}
    answers.update(extra)
    return JevResult(answers=answers, model="jev-1.13.0", input_tokens=1000)


PAPER = Paper(id="arxiv:1", source="arxiv", title="T", abstract="A", url="u")


@pytest.mark.parametrize(
    "ps, ex, band",
    [
        ({"agent_eval": 0.91, "calibration": 0.1}, 0.05, "must_read"),
        ({"agent_eval": 0.6, "calibration": 0.2}, 0.05, "maybe"),
        ({"agent_eval": 0.2, "calibration": 0.3}, 0.05, "skip"),
        ({"agent_eval": 0.99, "calibration": 0.9}, 0.75, "excluded"),
    ],
)
def test_bands(config, ps, ex, band):
    decision = decide(PAPER, _result(config, ps, {"medical_imaging": ex}), config)
    assert decision.band == band
    assert decision.paper_type == "benchmark" and decision.code == 0.9
    assert decision.cost == pytest.approx(1000 * 0.042 / 1e6)


def test_weights_and_noisy_or(tmp_path):
    config = make_config(
        tmp_path,
        interests=[{"id": "a", "text": "x", "weight": 0.5}, {"id": "b", "text": "y"}],
        exclude=[],
    )
    d = decide(PAPER, _result(config, {"a": 0.9, "b": 0.6}, {}), config)
    assert d.relevance == pytest.approx(0.6)
    assert combine([0.5, 0.5], "noisy_or") == pytest.approx(0.75)
    assert combine([], "max") == 0.0


def test_reported_cost_wins(config):
    result = _result(config, {"agent_eval": 0.9, "calibration": 0.1}, {"medical_imaging": 0.0})
    result.cost = 0.00002
    assert decide(PAPER, result, config).cost == 0.00002


def test_decision_roundtrip(config):
    d = decide(PAPER, _result(config, {"agent_eval": 0.9, "calibration": 0.1}, {"medical_imaging": 0.0}), config)
    from paper_radar.scoring import Decision

    again = Decision.from_dict(d.to_dict())
    assert again.relevance == pytest.approx(d.relevance) and again.band == d.band and again.paper.id == "arxiv:1"
    compact = Decision.from_dict(d.to_dict(full=False))
    assert compact.paper.abstract == ""


def test_parse_config_defaults(tmp_path):
    config = parse_config(
        {"sources": [{"type": "arxiv"}], "interests": [{"id": "a", "text": "x"}]}, base_dir=tmp_path
    )
    assert config.jev.backend == "typesafe" and config.thresholds.must_read == 0.8


def test_source_typos_are_rejected(tmp_path):
    with pytest.raises(ConfigError, match="catagories"):
        make_config(tmp_path, sources=[{"type": "arxiv", "catagories": ["cs.AI"]}])
    with pytest.raises(ConfigError, match="Unknown key"):
        make_config(tmp_path, sources=[{"type": "rss", "url": "https://e.org/f", "lmit": 5}])
    make_config(tmp_path, sources=[{"type": "biorxiv", "server": "biorxiv", "days": 2, "categories": ["neuroscience"]}])


def test_arxiv_without_categories_warns(tmp_path):
    config = make_config(tmp_path, sources=[{"type": "arxiv"}])
    assert any("no categories" in w for w in lint(config))


@pytest.mark.parametrize(
    "override, message",
    [
        ({"output": {"dedupe_days": 0}}, "dedupe_days"),
        ({"jev": {"backend": "mock", "price_per_mtok": -1}}, "price_per_mtok"),
        ({"summaries": {"enabled": True, "top_k": 0}}, "top_k"),
    ],
)
def test_numeric_guards(tmp_path, override, message):
    with pytest.raises(ConfigError, match=message):
        make_config(tmp_path, **override)
