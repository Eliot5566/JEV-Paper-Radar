import json
from datetime import date

import pytest

from paper_radar.config import ConfigError, JevSettings
from paper_radar.jev import JevError
from paper_radar.pipeline import run, run_screening
from paper_radar.questions import build_questions, build_screening_questions
from paper_radar.render import day_stats, render_archive
from paper_radar.usage import response_usage, summarize_usage
from tests.conftest import make_config
from tests.test_claude_backend import _backend, _claude_response, server_factory


def answers_for(questions):
    return {key: (0.9 if q["type"] == "noul" else next(iter(q["criteria"]))) for key, q in questions.items()}


def configured(tmp_path, **overrides):
    config = make_config(tmp_path, **overrides)
    config.jev.backend = "claude"
    config.jev.price_per_mtok = 0.1
    config.jev.output_price_per_mtok = 0.5
    config.jev.pricing_as_of = "2026-11-13"
    return config


def audit(config):
    return json.loads((config.data_path / "usage.jsonl").read_text().splitlines()[-1])


def test_repaired_reply_counts_both_requests_and_output_tokens(tmp_path, server_factory):
    config = configured(tmp_path)
    good = _claude_response(answers_for(build_questions(config)))
    bad = _claude_response({})
    good["usage"] = {"input_tokens": 800, "output_tokens": 60}
    server = server_factory([(200, {}, bad), (200, {}, good)])
    result = run(config, _backend(server.url), today=date(2026, 11, 13), limit=1, notify=False, log=lambda _: None)
    assert result.judged == 1 and result.failed == 0
    assert result.tokens == 1412
    assert result.cost == pytest.approx((1412 * 0.1 + 100 * 0.5) / 1e6)
    saved = audit(config)
    assert saved["requests"] == 2 and saved["output_tokens"] == 100
    assert saved["pricing_as_of"] == "2026-11-13"
    text = (config.data_path / "usage.jsonl").read_text()
    assert "sk-ant-test" not in text and '"answers"' not in text and '"abstract"' not in text
    assert result.decisions[0].input_tokens == 1412


def test_failed_judgement_still_records_charged_responses(tmp_path, server_factory):
    config = configured(tmp_path)
    server = server_factory([(200, {}, _claude_response({}))])
    result = run(config, _backend(server.url), today=date(2026, 11, 13), limit=1, notify=False, log=lambda _: None)
    assert result.judged == 0 and result.failed == 1
    assert result.tokens == 1224 and audit(config)["output_tokens"] == 80
    assert result.cost == pytest.approx((1224 * 0.1 + 80 * 0.5) / 1e6)


def test_fatal_error_persists_usage_and_does_not_invent_missing_charge(tmp_path, server_factory):
    config = configured(tmp_path)
    server = server_factory([(200, {}, _claude_response({})), (401, {}, {"error": "bad key"})])
    with pytest.raises(JevError):
        run(config, _backend(server.url), today=date(2026, 11, 13), limit=1, notify=False, log=lambda _: None)
    saved = audit(config)
    assert saved["requests"] == 2 and saved["input_tokens"] == 612
    assert saved["cost_usd"] is None and saved["usage_complete"] is False
    assert saved["known_cost_usd"] == pytest.approx((612 * 0.1 + 40 * 0.5) / 1e6)


def test_screening_also_writes_usage_audit(tmp_path, server_factory):
    config = configured(tmp_path, screening={"enabled": True, "include": [{"id": "a", "text": "About agents"}]})
    server = server_factory([(200, {}, _claude_response(answers_for(build_screening_questions(config))))])
    result = run_screening(config, _backend(server.url), today=date(2026, 11, 13), limit=1, log=lambda _: None)
    assert result.screened == 1 and audit(config)["requests"] == 1
    assert result.cost == pytest.approx((612 * 0.1 + 40 * 0.5) / 1e6)


def test_nonzero_cache_usage_needs_its_own_rate():
    record = response_usage({"usage": {"input_tokens": 100, "output_tokens": 10, "cache_read_input_tokens": 200}})
    settings = JevSettings(backend="claude", price_per_mtok=0.1, output_price_per_mtok=0.5)
    assert summarize_usage([record], settings)["cost_usd"] is None
    settings.cache_read_price_per_mtok = 0.01
    assert summarize_usage([record], settings)["cost_usd"] == pytest.approx((100 * 0.1 + 10 * 0.5 + 200 * 0.01) / 1e6)


def test_missing_output_rate_is_unknown_but_provider_reported_cost_wins():
    record = response_usage({"usage": {"input_tokens": 100, "output_tokens": 10}})
    settings = JevSettings(backend="claude")
    assert summarize_usage([record], settings)["cost_usd"] is None
    record["reported_cost_usd"] = 0.0001
    assert summarize_usage([record], settings)["cost_usd"] == 0.0001


def test_known_free_output_does_not_need_an_output_count():
    record = response_usage({"usage": {"input_tokens": 100}})
    summary = summarize_usage([record], JevSettings(backend="typesafe"))
    assert summary["cost_usd"] == pytest.approx(100 * 0.042 / 1e6)
    assert summary["usage_complete"] is False


@pytest.mark.parametrize("value", [-1, True, float("nan"), float("inf"), "cheap"])
def test_invalid_rates_are_rejected(tmp_path, value):
    with pytest.raises(ConfigError, match="output_price_per_mtok"):
        make_config(tmp_path, jev={"backend": "mock", "output_price_per_mtok": value})


def test_historical_partial_cost_does_not_become_a_full_bill(config):
    old = {"day": "2026-11-13", "judged": 1, "input_tokens": 100, "cost_usd": 0.01}
    stats = day_stats("2026-11-13", [], [old])
    assert stats["cost"] is None
    assert "cost unknown" in render_archive(config, [("2026-11-13", stats)])
    from paper_radar.render import render_directory
    entry = dict(stats, day="2026-11-13", title="Radar", tagline="", url="./", feed="./feed.xml", shortlisted=0, top=[])
    assert "cost unknown" in render_directory([entry])


def test_same_day_reruns_accumulate_billed_requests():
    rows = [{"day": "2026-11-13", "judged": 1, "input_tokens": n, "cost_usd": cost, "billing": {"requests": 1}}
            for n, cost in [(100, 0.01), (200, 0.02)]]
    stats = day_stats("2026-11-13", [], rows)
    assert stats["tokens"] == 300 and stats["cost"] == pytest.approx(0.03)


def test_day_cost_includes_aborted_attempts_without_double_counting():
    runs = [{"day": "2026-11-13", "judged": 1, "input_tokens": 100, "cost_usd": 0.01, "billing": {"requests": 1}}]
    audits = [{"day": "2026-11-13", "input_tokens": 100, "cost_usd": 0.01, "requests": 1},
              {"day": "2026-11-13", "input_tokens": 200, "cost_usd": 0.02, "requests": 1}]
    stats = day_stats("2026-11-13", [], runs, audits)
    assert stats["tokens"] == 300 and stats["cost"] == pytest.approx(0.03)
    audits[-1]["cost_usd"] = None
    assert day_stats("2026-11-13", [], runs, audits)["cost"] is None


def test_missing_audit_file_does_not_make_a_recorded_run_free():
    runs = [{"day": "2026-11-13", "judged": 1, "input_tokens": 100, "cost_usd": 0.01, "billing": {"requests": 1}}]
    stats = day_stats("2026-11-13", [], runs, [])
    assert stats["cost"] is None and stats["tokens"] == 100
