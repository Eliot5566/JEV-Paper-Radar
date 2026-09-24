"""PubMed source and systematic-review screening mode."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from paper_radar.config import ConfigError, lint, parse_config
from paper_radar.ids import normalize_paper_id
from paper_radar.jev import MockBackend
from paper_radar.models import JevResult, Paper
from paper_radar.pipeline import run_screening
from paper_radar.questions import build_screening_questions
from paper_radar.screening import (
    EXCLUDE,
    EXCLUDE_CRITERION,
    INCLUDE,
    MANUAL,
    format_performance,
    format_prisma,
    prisma_counts,
    screen,
    screening_performance,
)
from paper_radar.sources.pubmed import DEFAULT_EXCLUDE_TYPES, parse_esearch, parse_pubmed
from paper_radar.store import Store

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pubmed_efetch.xml"
DAY = date(2026, 9, 24)


def quiet(_):
    pass


# ── the PubMed source ────────────────────────────────────────────────────────────

def test_parse_esearch_reads_the_id_list():
    payload = json.dumps(
        {"header": {"type": "esearch"}, "esearchresult": {"count": "78", "retmax": "3", "idlist": ["42777254", "42777185"]}}
    )
    assert parse_esearch(payload) == ["42777254", "42777185"]


def test_parse_esearch_surfaces_ncbi_errors():
    with pytest.raises(ValueError, match="Invalid db name"):
        parse_esearch(json.dumps({"esearchresult": {"ERROR": "Invalid db name"}}))


def test_parse_pubmed_covers_the_awkward_records():
    papers = parse_pubmed(FIXTURE.read_text(encoding="utf-8"), set(DEFAULT_EXCLUDE_TYPES))
    by_id = {p.id: p for p in papers}

    # The erratum is dropped: it is a correction notice, not a new study.
    assert "pubmed:42776597" not in by_id
    assert set(by_id) == {"pubmed:42777254", "pubmed:42777185", "pubmed:42777157"}

    plain = by_id["pubmed:42777254"]
    assert plain.url == "https://pubmed.ncbi.nlm.nih.gov/42777254/"
    assert plain.abstract.startswith("A retrospective cohort study")
    assert plain.authors == ["Wang L", "Chen M"]
    assert plain.categories == ["J Cardiovasc Pharmacol Ther"]
    assert plain.published == "2026-Sep"

    # A structured abstract keeps its section labels: criteria often target the methods.
    structured = by_id["pubmed:42777185"]
    assert "Background And Objectives: Stroke in young adults" in structured.abstract
    assert "Methods: We conducted a randomised controlled trial" in structured.abstract
    assert structured.authors == ["The YOUNG-STROKE Investigators"]

    # Kept, not dropped — a review has to account for it.
    assert by_id["pubmed:42777157"].abstract == ""


def test_parse_pubmed_keeps_errata_when_asked():
    papers = parse_pubmed(FIXTURE.read_text(encoding="utf-8"), set())
    assert "pubmed:42776597" in {p.id for p in papers}


def test_parse_pubmed_rejects_garbage():
    with pytest.raises(ValueError, match="unparseable XML"):
        parse_pubmed("<PubmedArticleSet>truncated")


def test_pubmed_ids_normalize():
    assert normalize_paper_id("42777254") == "pubmed:42777254"
    assert normalize_paper_id("https://pubmed.ncbi.nlm.nih.gov/42777254/") == "pubmed:42777254"
    assert normalize_paper_id("2609.01234") == "arxiv:2609.01234"  # still unambiguous


def test_pubmed_source_needs_a_query():
    with pytest.raises(ConfigError, match="needs a query"):
        parse_config({"sources": [{"type": "pubmed"}], "interests": [{"id": "a", "text": "x"}]})


def test_pubmed_source_warns_without_an_email():
    config = parse_config({
        "sources": [{"type": "pubmed", "query": "cancer[Title]"}],
        "interests": [{"id": "a", "text": "x"}],
    })
    assert any("NCBI asks callers to identify themselves" in w for w in lint(config))


# ── screening configuration ──────────────────────────────────────────────────────

def review_config(tmp_path: Path, **screening):
    raw = {
        "jev": {"backend": "mock"},
        "sources": [{"type": "pubmed", "file": str(FIXTURE), "query": "unused"}],
        "screening": {
            "enabled": True,
            "include": [
                {"id": "population", "text": "The study enrolls adults with atrial fibrillation"},
                {"id": "design", "text": "The study is a randomised controlled trial"},
            ],
            "exclude": [{"id": "animal", "text": "The study is conducted only in animals"}],
            **screening,
        },
    }
    return parse_config(raw, base_dir=tmp_path)


def test_screening_config_needs_include_criteria(tmp_path):
    with pytest.raises(ConfigError, match="no \\[\\[screening.include\\]\\] criteria"):
        parse_config({"jev": {"backend": "mock"},
                      "sources": [{"type": "arxiv", "file": "x"}],
                      "screening": {"enabled": True}}, base_dir=tmp_path)


def test_screening_replaces_the_need_for_interests(tmp_path):
    config = review_config(tmp_path)
    assert config.interests == [] and config.screening.enabled


def test_screening_rejects_unknown_keys(tmp_path):
    with pytest.raises(ConfigError, match="Unknown key\\(s\\) in \\[screening\\]"):
        parse_config({"sources": [{"type": "arxiv", "file": "x"}],
                      "screening": {"enabled": True, "recall_target": 0.9,
                                    "include": [{"id": "a", "text": "x"}]}}, base_dir=tmp_path)


def test_screening_questions_are_only_criteria(tmp_path):
    questions = build_screening_questions(review_config(tmp_path))
    assert set(questions) == {"si_population", "si_design", "sx_animal"}
    assert all(q["type"] == "noul" for q in questions.values())


def test_include_criterion_negation_is_linted(tmp_path):
    config = review_config(tmp_path, include=[{"id": "p", "text": "The study does not enrol children"}])
    assert any("screening.include 'p' contains a negation" in w for w in lint(config))


# ── screening decisions ──────────────────────────────────────────────────────────

def decision_for(tmp_path, probabilities, *, abstract="An abstract.", **screening):
    """Build one ScreenDecision from a dict of raw Noul answers."""
    config = review_config(tmp_path, **screening)
    paper = Paper(id="pubmed:1", source="pubmed", title="T", abstract=abstract, url="u")
    answers = {key: {"noul": value} for key, value in probabilities.items()}
    return screen(paper, JevResult(answers=answers, model="m", input_tokens=10), config)


def test_min_mode_scores_the_weakest_criterion(tmp_path):
    d = decision_for(tmp_path, {"si_population": 0.95, "si_design": 0.62, "sx_animal": 0.01},
                     combine="min")
    assert d.eligibility == pytest.approx(0.62) and d.weakest == "design"
    assert d.verdict == INCLUDE


def test_geometric_mode_uses_every_criterion(tmp_path):
    """The reason the default changed: min() cannot tell these two records apart."""
    strong = {"si_population": 0.95, "si_design": 0.02, "sx_animal": 0.0}
    weak = {"si_population": 0.10, "si_design": 0.02, "sx_animal": 0.0}

    assert decision_for(tmp_path, strong, combine="min").eligibility == pytest.approx(
        decision_for(tmp_path, weak, combine="min").eligibility)

    a = decision_for(tmp_path, strong)
    b = decision_for(tmp_path, weak)
    assert a.eligibility > b.eligibility
    assert a.weakest == "design" and b.weakest == "design"   # still reported, for diagnosis


def test_geometric_score_does_not_drift_with_the_number_of_criteria(tmp_path):
    """A threshold has to mean the same thing in a 3-criterion and a 6-criterion review."""
    from paper_radar.screening import combine_criteria

    assert combine_criteria([0.9] * 3) == pytest.approx(combine_criteria([0.9] * 6))
    assert combine_criteria([0.9] * 3, "min") == pytest.approx(combine_criteria([0.9] * 6, "min"))


def test_a_criterion_near_zero_still_sinks_the_record(tmp_path):
    """Geometric is still a conjunction: it is not an average that forgives a failure."""
    d = decision_for(tmp_path, {"si_population": 0.99, "si_design": 0.001, "sx_animal": 0.0})
    assert d.verdict == EXCLUDE and d.eligibility < 0.11


def test_an_exclusion_criterion_beats_a_high_eligibility(tmp_path):
    d = decision_for(tmp_path, {"si_population": 0.99, "si_design": 0.99, "sx_animal": 0.97})
    assert d.verdict == EXCLUDE_CRITERION and d.triggered == ["animal"]


def test_a_record_without_an_abstract_is_never_auto_excluded(tmp_path):
    d = decision_for(tmp_path, {"si_population": 0.01, "si_design": 0.01, "sx_animal": 0.99}, abstract="   ")
    assert d.verdict == MANUAL and not d.screened


# ── PRISMA counts ────────────────────────────────────────────────────────────────

def test_prisma_counts_separate_automation_from_everything_else(tmp_path):
    decisions = [
        decision_for(tmp_path, {"si_population": 0.9, "si_design": 0.9, "sx_animal": 0.0}),
        decision_for(tmp_path, {"si_population": 0.9, "si_design": 0.1, "sx_animal": 0.0}),
        decision_for(tmp_path, {"si_population": 0.9, "si_design": 0.9, "sx_animal": 0.95}),
        decision_for(tmp_path, {"si_population": 0.9, "si_design": 0.9, "sx_animal": 0.0}, abstract=""),
    ]
    counts = prisma_counts(decisions, identified=10, duplicates=6)
    assert counts["identified"] == 10 and counts["duplicates_removed"] == 6
    assert counts["screened"] == 4
    assert counts["sought_for_retrieval"] == 1
    assert counts["automation_excluded"] == 2
    assert counts["excluded_by_criterion"] == 1 and counts["excluded_low_eligibility"] == 1
    assert counts["manual_review"] == 1
    assert counts["exclusion_reasons"] == {"animal": 1}

    text = format_prisma(counts)
    assert "Records marked ineligible by this tool" in text
    assert "not a completed screen" in text


# ── performance against a human screener ────────────────────────────────────────

def test_threshold_is_fitted_to_the_recall_target():
    # 20 eligible studies scored 0.80..0.99, 80 ineligible scored 0.00..0.79.
    eligibility = {f"p{i}": i / 100 for i in range(100)}
    labels = {f"p{i}": i >= 80 for i in range(100)}
    report = screening_performance(eligibility, labels, target_recall=0.95)
    assert report.n == 100 and report.positives == 20
    assert report.recall >= 0.95
    assert report.precision == pytest.approx(1.0)
    # Threshold lands at 0.81, so 80 true negatives and 1 missed study go unread:
    # WSS@95 = (80 + 1)/100 - (1 - 0.95) = 0.76.
    assert report.threshold == pytest.approx(0.81)
    assert report.workload_saved == pytest.approx(0.76)
    assert report.missed == ["p80"]
    assert "Workload saved (WSS)" in format_performance(report)


def test_performance_names_the_studies_the_threshold_would_miss():
    eligibility = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.1, "e": 0.05}
    labels = {"a": True, "b": True, "c": True, "d": True, "e": False}
    report = screening_performance(eligibility, labels, target_recall=0.75)
    assert "d" in report.missed
    assert "Read these before trusting the threshold" in format_performance(report)


def test_performance_warns_instead_of_inventing_a_number():
    empty = screening_performance({}, {"a": True})
    assert empty.n == 0 and any("no stored decision" in w for w in empty.warnings)
    assert "Screening performance" in format_performance(empty)

    no_positives = screening_performance({"a": 0.5}, {"a": False})
    assert any("No eligible studies" in w for w in no_positives.warnings)

    small = screening_performance({"a": 0.9, "b": 0.1}, {"a": True, "b": False})
    assert any("rough" in w for w in small.warnings)


# ── end to end ───────────────────────────────────────────────────────────────────

def test_screening_run_end_to_end(tmp_path):
    config = review_config(tmp_path)
    result = run_screening(config, MockBackend(), today=DAY, log=quiet)

    # Three records survive the erratum filter; the one with no abstract never reaches Jev.
    assert result.fetched == 3 and result.screened == 3
    assert result.counts["manual_review"] == 1
    assert sum(1 for d in result.decisions if d.verdict == MANUAL) == 1
    assert all(d.input_tokens == 0 for d in result.decisions if d.verdict == MANUAL)

    stored = Store(config.data_path).load_screening("2026-09-24")
    assert len(stored) == 3
    assert {r["paper"]["id"] for r in stored} == {"pubmed:42777254", "pubmed:42777185", "pubmed:42777157"}
    # Every screened record is kept in full, including the rejects.
    assert (config.data_path / "screening" / "2026-09-24.jsonl").exists()


def test_a_record_is_screened_once_and_never_again(tmp_path):
    config = review_config(tmp_path)
    run_screening(config, MockBackend(), today=DAY, log=quiet)
    again = run_screening(config, MockBackend(), today=date(2026, 9, 25), log=quiet)
    assert again.screened == 0 and again.counts["duplicates_removed"] == 3


# ── the CLI ──────────────────────────────────────────────────────────────────────

def test_screen_refuses_a_config_that_is_not_a_review(tmp_path, capsys):
    from paper_radar.cli import main

    cfg = tmp_path / "radar.toml"
    cfg.write_text('[[sources]]\ntype = "arxiv"\n[[interests]]\nid = "a"\ntext = "x"\n', encoding="utf-8")
    assert main(["screen", "-c", str(cfg)]) == 2
    assert "[screening] is not enabled" in capsys.readouterr().err


def test_check_reports_screening_mode(tmp_path, capsys):
    from paper_radar.cli import main

    cfg = tmp_path / "review.toml"
    cfg.write_text(
        f'[jev]\nbackend = "mock"\n'
        f'[[sources]]\ntype = "pubmed"\nfile = "{FIXTURE.as_posix()}"\nquery = "x"\n'
        '[screening]\nenabled = true\n'
        '[[screening.include]]\nid = "population"\ntext = "The study enrolls adults"\n',
        encoding="utf-8",
    )
    assert main(["check", "-c", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "screening mode): 1 include criteria" in out and "paper-radar screen -c" in out


def test_screen_report_runs_without_any_labels(tmp_path, capsys):
    from paper_radar.cli import main

    config = review_config(tmp_path)
    run_screening(config, MockBackend(), today=DAY, log=quiet)
    cfg = tmp_path / "review.toml"
    cfg.write_text(
        f'[jev]\nbackend = "mock"\n'
        f'[[sources]]\ntype = "pubmed"\nfile = "{FIXTURE.as_posix()}"\nquery = "x"\n'
        f'[output]\ndata_dir = "{config.data_path.as_posix()}"\n'
        '[screening]\nenabled = true\n'
        '[[screening.include]]\nid = "population"\ntext = "The study enrolls adults"\n',
        encoding="utf-8",
    )
    assert main(["screen", "-c", str(cfg), "--report"]) == 0
    assert "No labelled records overlap" in capsys.readouterr().out


# ── the benchmark's criteria files ──────────────────────────────────────────────

def test_every_benchmark_criteria_file_is_valid():
    """A typo in a criteria file would silently change a published number."""
    import tomllib

    folder = Path(__file__).resolve().parents[1] / "benchmarks" / "clef_tar_2019" / "criteria"
    files = sorted(folder.glob("*/*.toml"))
    assert len(files) >= 16   # v1 (literal) and v2 (revised) must both stay valid

    for path in files:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        meta = raw.pop("benchmark")
        assert meta["topic"] == path.stem
        assert meta["review_pmid"].isdigit()
        raw["jev"] = {"backend": "mock"}
        raw["sources"] = [{"type": "pubmed", "query": "placeholder"}]
        config = parse_config(raw, base_dir=folder)
        assert config.screening.enabled and config.screening.include
        # The published criteria must be quoted in the file, so the translation is checkable.
        assert "SELECTION CRITERIA, as published:" in path.read_text(encoding="utf-8")
        # And the criteria themselves must survive the project's own lint.
        assert not [w for w in lint(config) if "screening.include" in w], path.name
