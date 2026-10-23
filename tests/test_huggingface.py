"""Hugging Face Daily Papers, and the merge that lets it add upvotes to an arXiv paper."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from paper_radar.models import Paper
from paper_radar.sources import _merge, collect
from paper_radar.sources.huggingface import fetch_huggingface, parse_daily_papers

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DAILY = json.loads((FIXTURES / "hf_daily_papers.json").read_text(encoding="utf-8"))
DEMO = Path(__file__).resolve().parents[1] / "paper_radar" / "demo" / "arxiv_demo.xml"


def _quiet(_):
    pass


def test_parse_maps_onto_an_arxiv_id_so_it_can_dedupe():
    papers = {p.id: p for p in parse_daily_papers(DAILY)}
    hf = papers["arxiv:2609.99001"]
    assert hf.source == "huggingface"
    assert hf.url == "https://arxiv.org/abs/2609.99001"
    assert hf.discussion == "https://huggingface.co/papers/2609.99001"
    assert hf.metrics == {"upvotes": 411, "comments": 3}
    assert hf.title == "TraceGrade: Evaluating LLM Agents on Long-Horizon Tool-Use Tasks"
    assert hf.abstract == "We introduce TraceGrade, a benchmark for agents."
    assert hf.authors == ["Ada Example"], "hidden authors stay hidden"
    # The model judges the authors' abstract; HF's AI-written summary is never used.
    assert "Not used" not in hf.abstract


def test_upvote_floor():
    assert {p.id for p in parse_daily_papers(DAILY, min_upvotes=10)} == {"arxiv:2609.99001", "arxiv:2610.28577"}


def test_fetch_reaches_back_far_enough_for_a_monday_and_dedupes_across_days(tmp_path):
    calls: list[str] = []

    def getter(url: str) -> str:
        calls.append(url)
        # Saturday and Sunday lists are empty arrays on the live API, not errors.
        if "2026-10-18" in url or "2026-10-17" in url:
            return "[]"
        return json.dumps(DAILY)   # the same papers on Monday and Friday

    papers = fetch_huggingface({"type": "huggingface"}, getter=getter, base_dir=tmp_path, today=date(2026, 10, 19))
    assert [u.split("date=")[1].split("&")[0] for u in calls] == ["2026-10-19", "2026-10-18", "2026-10-17", "2026-10-16"]
    assert all("limit=100" in u for u in calls), "the API's default page is 50"
    assert len(papers) == 3, "a paper listed on two days is one item"


def test_an_empty_body_is_reported_as_such(tmp_path):
    with pytest.raises(ValueError, match="empty response"):
        fetch_huggingface({"type": "huggingface", "days": 1}, getter=lambda u: "", base_dir=tmp_path, today=date(2026, 10, 23))


def test_a_non_list_response_is_an_error_not_an_empty_day():
    with pytest.raises(ValueError, match="did not return a list"):
        parse_daily_papers({"error": "rate limited"})


def test_collect_merges_upvotes_into_the_arxiv_copy_in_either_order(tmp_path):
    """The arXiv record carries categories the model reads; HF carries the upvotes and a
    discussion page. Whichever source the config lists first, the result has both."""
    hf_file = tmp_path / "hf.json"
    hf_file.write_text(json.dumps(DAILY), encoding="utf-8")
    arxiv = {"type": "arxiv", "file": str(DEMO)}
    hf = {"type": "huggingface", "file": str(hf_file)}

    for order in ([arxiv, hf], [hf, arxiv]):
        papers = {p.id: p for p in collect(order, today=date(2026, 9, 22), base_dir=tmp_path, log=_quiet)}
        merged = papers["arxiv:2609.99001"]
        assert merged.metrics.get("upvotes") == 411
        assert merged.discussion == "https://huggingface.co/papers/2609.99001"
        assert merged.categories == ["cs.CL", "cs.AI"]
        # 44 demo papers + the two HF papers the demo feed does not have
        assert len(papers) == 46


def test_merge_never_overwrites_what_the_first_copy_has():
    kept = Paper(id="x", source="arxiv", title="T", abstract="A", url="u", categories=["cs.CL"],
                 discussion="d1", metrics={"upvotes": 1})
    _merge(kept, Paper(id="x", source="hf", title="T2", abstract="B", url="u2", categories=["z"],
                       discussion="d2", metrics={"upvotes": 99, "comments": 4}))
    assert (kept.title, kept.abstract, kept.categories, kept.discussion) == ("T", "A", ["cs.CL"], "d1")
    assert kept.metrics == {"upvotes": 1, "comments": 4}


def test_config_accepts_the_source():
    from paper_radar.config import parse_config

    config = parse_config({
        "sources": [{"type": "huggingface", "days": 4, "min_upvotes": 10}],
        "interests": [{"id": "x", "text": "y"}],
    })
    assert config.sources[0]["type"] == "huggingface"


def test_upvote_is_singular_when_there_is_one():
    from paper_radar.render import _metric

    assert _metric("upvotes", 1) == "1 upvote" and _metric("upvotes", 411) == "411 upvotes"
