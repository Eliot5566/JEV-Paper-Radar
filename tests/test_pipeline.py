import gzip
import json
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest

from paper_radar.calibrate import calibrate, format_report
from paper_radar.jev import JevError, MockBackend
from paper_radar.notify import send_all
from paper_radar.pipeline import rebuild_site, run
from paper_radar.store import Store
from paper_radar.summarize import summarize_top

DAY = date(2026, 9, 22)
DEMO = Path(__file__).resolve().parents[1] / "paper_radar" / "demo" / "arxiv_demo.xml"


def quiet(_):
    pass


def test_end_to_end_mock(config):
    result = run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    counts = result.counts()
    assert result.judged == 44 and result.failed == 0
    assert counts["must_read"] >= 3 and counts["excluded"] == 1
    site = config.site_path
    for name in ("index.html", "2026-09-22.html", "archive.html", "feed.xml", ".nojekyll"):
        assert (site / name).exists(), name
    page = (site / "index.html").read_text(encoding="utf-8")
    assert "Offline demo" in page and "TraceGrade" in page
    feed = ET.fromstring((site / "feed.xml").read_text(encoding="utf-8"))
    titles = [i.findtext("title") for i in feed.iter("item")]
    assert len(titles) == counts["must_read"] + counts["maybe"]
    assert any(t.startswith("★ ") for t in titles)

    data = config.data_path / "decisions"
    shown = [json.loads(line) for line in (data / "2026-09-22.jsonl").open(encoding="utf-8")]
    rest = [json.loads(line) for line in gzip.open(data / "2026-09-22.rest.jsonl.gz", "rt")]
    assert {r["band"] for r in shown} <= {"must_read", "maybe"}
    assert all("abstract" not in r["paper"] for r in rest)
    run_log = Store(config.data_path).load_runs()
    assert run_log[-1]["judged"] == 44 and run_log[-1]["backend"] == "mock"


def test_second_run_same_day_skips_seen(config):
    run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    again = run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    assert again.judged == 0
    assert len(Store(config.data_path).load_decisions("2026-09-22")) == 44


def test_dry_run_calls_nothing(config):
    class Exploding(MockBackend):
        def decide(self, state, questions):
            raise AssertionError("should not be called")

    result = run(config, Exploding(), today=DAY, dry_run=True, notify=False, log=quiet)
    assert result.fetched == 44 and result.judged == 0


def test_limit(config):
    assert run(config, MockBackend(), today=DAY, limit=5, notify=False, log=quiet).judged == 5


def test_fatal_error_aborts(config):
    class Unauthorized(MockBackend):
        name = "typesafe"

        def decide(self, state, questions):
            raise JevError("typesafe HTTP 401: bad key", fatal=True, status=401)

    with pytest.raises(JevError, match="401"):
        run(config, Unauthorized(), today=DAY, notify=False, log=quiet)
    assert Store(config.data_path).days() == []


def test_transient_failures_are_retried_next_run(config):
    class Flaky(MockBackend):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def decide(self, state, questions):
            self.calls += 1
            if "TraceGrade" in state["title"]:
                raise JevError("timeout")
            return super().decide(state, questions)

    first = run(config, Flaky(), today=DAY, notify=False, log=quiet)
    assert first.failed == 1 and first.judged == 43
    second = run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    assert second.judged == 1


def test_notifications(config):
    result = run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    posts = []
    env = {"SLACK_WEBHOOK_URL": "https://hooks/slack", "DISCORD_WEBHOOK_URL": "https://hooks/discord",
           "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "42"}
    sent = send_all(config, "2026-09-22", result.decisions, env=env, poster=lambda url, payload, **kw: posts.append((url, payload)), log=quiet)
    assert sent == ["slack", "discord", "telegram"]
    assert "shortlisted" in posts[0][1]["text"] and "<" in posts[0][1]["text"]
    assert len(posts[1][1]["content"]) <= 1990
    assert posts[2][0] == "https://api.telegram.org/bott/sendMessage" and posts[2][1]["chat_id"] == "42"
    assert send_all(config, "d", result.decisions, env={}, log=quiet) == []


def test_notification_failure_is_not_fatal(config):
    result = run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    logs = []

    def broken(*a, **k):
        raise OSError("down")

    assert send_all(config, "d", result.decisions, env={"SLACK_WEBHOOK_URL": "x"}, poster=broken, log=logs.append) == []
    assert "slack notification failed" in logs[0]


def test_summaries_cascade(tmp_path):
    from .conftest import make_config

    config = make_config(tmp_path, summaries={"enabled": True, "model": "some-llm", "language": "Traditional Chinese", "top_k": 2})
    result = run(config, MockBackend(), today=DAY, notify=False, log=quiet, env={})  # no key -> skipped
    assert all(d.summary is None for d in result.decisions)
    calls = []

    def poster(url, payload, **kw):
        calls.append((url, payload, kw))
        return {"choices": [{"message": {"content": "一句話摘要。"}}]}

    n = summarize_top(config.summaries, result.decisions, env={"LLM_API_KEY": "k"}, poster=poster, log=quiet)
    assert n == 2 and calls[0][0] == "https://api.openai.com/v1/chat/completions"
    assert "Traditional Chinese" in calls[0][1]["messages"][0]["content"]
    assert calls[0][2]["headers"]["Authorization"] == "Bearer k"


def test_rebuild_without_runs(config):
    rebuild_site(config, Store(config.data_path))
    assert "No runs yet" in (config.site_path / "index.html").read_text(encoding="utf-8")


def test_calibrate_suggests_thresholds():
    relevance = {f"p{i}": i / 100 for i in range(100)}
    labels = {f"p{i}": i >= 70 for i in range(100)}
    report = calibrate(relevance, labels, target_precision=0.95, target_recall=0.9)
    assert report.n == 100 and report.positives == 30
    assert report.suggested_must_read == pytest.approx(0.7)
    assert report.suggested_maybe == pytest.approx(0.7)
    text = format_report(report, 0.95, 0.9)
    assert "Brier" in text and "Suggested must_read" in text


def test_calibrate_small_sample_warns():
    report = calibrate({"a": 0.9}, {"a": True, "missing": False})
    assert any("rough" in w for w in report.warnings) and any("no stored decision" in w for w in report.warnings)


def test_quiet_day_still_builds_site(tmp_path):
    from .conftest import make_config

    empty = tmp_path / "empty.xml"
    empty.write_text('<rss version="2.0"><channel></channel></rss>', encoding="utf-8")
    config = make_config(tmp_path, sources=[{"type": "arxiv", "file": str(empty)}])
    result = run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    assert result.judged == 0 and (config.site_path / "index.html").exists()
    # data/ and a run record must exist so the workflow's `git add data` step works
    runs = Store(config.data_path).load_runs()
    assert runs[-1]["judged"] == 0 and runs[-1]["fetched"] == 0
    assert (config.data_path / "runs.jsonl").exists()


def test_untrusted_links_are_neutralized(config):
    from paper_radar.models import Paper
    from paper_radar.render import day_stats, render_day
    from paper_radar.scoring import Decision

    evil = Decision(paper=Paper(id="rss:x", source="rss", title="<script>alert(1)</script>", abstract="a",
                                url="javascript:alert(1)"), relevance=0.9, band="must_read", interests={"agent_eval": 0.9}, exclusions={})
    page = render_day(config, "2026-09-22", [evil], day_stats("2026-09-22", [evil], []))
    assert "javascript:" not in page and "<script>alert" not in page


def test_vote_links_appear_only_when_configured(tmp_path):
    from urllib.parse import unquote

    from .conftest import make_config

    config = make_config(tmp_path, output={"feedback_repo": "Eliot5566/JEV-Paper-Radar"})
    run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    page = (config.site_path / "index.html").read_text(encoding="utf-8")
    assert "issues/new?title=" in page and "👍" in page and "👎" in page
    assert unquote(page.split("issues/new?title=")[1].split('"')[0]).startswith("radar-label: arxiv:2609.9")

    plain = make_config(tmp_path / "plain")
    run(plain, MockBackend(), today=DAY, notify=False, log=quiet)
    assert "issues/new" not in (plain.site_path / "index.html").read_text(encoding="utf-8")


def test_harvest_records_labels_and_closes_issues(config):
    from paper_radar.feedback import harvest

    issues = [
        {"number": 1, "title": "radar-label: 2609.99001 yes", "created_at": "2026-09-23T01:00:00Z"},
        {"number": 2, "title": "radar-label: arxiv:2609.99007 NO", "created_at": "2026-09-23T02:00:00Z"},
        {"number": 3, "title": "Feature request: add PubMed"},
        {"number": 4, "title": "radar-label: 2609.99002 yes", "pull_request": {}},
    ]
    patched = []
    store = Store(config.data_path)
    result = harvest(
        "owner/name",
        store,
        token="t",
        fetch=lambda url, headers: (headers["Authorization"] == "Bearer t" and "state=open" in url) and issues or [],
        patch=lambda url, payload, headers: patched.append((url, payload)),
        log=quiet,
    )
    assert result.recorded == 2 and result.closed == 2 and result.ignored == 1
    assert store.load_labels() == {"arxiv:2609.99001": True, "arxiv:2609.99007": False}
    assert patched[0][1]["state"] == "closed" and patched[0][0].endswith("/issues/1")


def test_harvest_without_token_keeps_issues_open(config):
    from paper_radar.feedback import harvest

    issues = [{"number": 9, "title": "radar-label: 2609.99001 yes"}]
    result = harvest("o/n", Store(config.data_path), close=False, fetch=lambda url, h: issues,
                     patch=lambda *a: (_ for _ in ()).throw(AssertionError("must not close")), log=quiet)
    assert result.recorded == 1 and result.closed == 0


def test_harvest_rejects_bad_repo(config):
    from paper_radar.feedback import harvest

    with pytest.raises(ValueError, match="owner/name"):
        harvest("not-a-repo", Store(config.data_path), fetch=lambda url, h: [], log=quiet)


def test_custom_tagline(tmp_path):
    from .conftest import make_config

    config = make_config(tmp_path, output={"tagline": "Today's standouts across AI."})
    run(config, MockBackend(), today=DAY, notify=False, log=quiet)
    page = (config.site_path / "index.html").read_text(encoding="utf-8")
    assert "Today&#x27;s standouts across AI." in page and "against your interests" not in page


def test_directory_lists_every_radar_with_its_own_numbers(tmp_path, capsys):
    """The directory page is what a visitor lands on, so an empty or wrong one is a
    silent failure of the whole public-feeds idea."""
    from paper_radar.cli import main

    live = tmp_path / "live.toml"
    live.write_text(
        f'[jev]\nbackend = "mock"\n'
        f'[[sources]]\ntype = "arxiv"\nfile = "{DEMO.as_posix()}"\n'
        '[[interests]]\nid = "agent_eval"\ntext = "Benchmarks for evaluating LLM agents"\n'
        f'[output]\nsite_dir = "{(tmp_path / "site" / "live").as_posix()}"\n'
        f'data_dir = "{(tmp_path / "data" / "live").as_posix()}"\n'
        'tagline = "Live feed tagline."\n',
        encoding="utf-8",
    )
    empty = tmp_path / "empty.toml"
    empty.write_text(
        f'[radar]\ntitle = "Never Run"\n[jev]\nbackend = "mock"\n'
        f'[[sources]]\ntype = "arxiv"\nfile = "{DEMO.as_posix()}"\n'
        '[[interests]]\nid = "x"\ntext = "y"\n'
        f'[output]\nsite_dir = "{(tmp_path / "site" / "empty").as_posix()}"\n'
        f'data_dir = "{(tmp_path / "data" / "empty").as_posix()}"\n',
        encoding="utf-8",
    )
    assert main(["run", "-c", str(live), "--date", "2026-09-22", "--no-notify"]) == 0

    out = tmp_path / "index.html"
    assert main(["directory", "--out", str(out), str(live), str(empty)]) == 0
    page = out.read_text(encoding="utf-8")

    assert "Live feed tagline." in page and "Never Run" in page
    assert "worth opening" in page and "No run recorded yet." in page   # both states render
    assert 'href="./live/"' in page and 'href="./live/feed.xml"' in page
    assert "TraceGrade" in page          # a real pick from today, not a placeholder
    assert "Fork it" in page             # the page has to convert readers into users
    assert "wrote" in capsys.readouterr().out


def test_base_dir_override_puts_output_where_it_is_published(tmp_path):
    """A config in a subfolder resolves site_dir against that subfolder, which silently
    publishes nothing. This cost a day of six radars writing into radars/site/."""
    from paper_radar.cli import main

    folder = tmp_path / "radars"
    folder.mkdir()
    (folder / "x.toml").write_text(
        f'[jev]\nbackend = "mock"\n'
        f'[[sources]]\ntype = "arxiv"\nfile = "{DEMO.as_posix()}"\n'
        '[[interests]]\nid = "agent_eval"\ntext = "Benchmarks for evaluating LLM agents"\n'
        '[output]\nsite_dir = "site/out"\ndata_dir = "data/out"\n',
        encoding="utf-8",
    )
    # without the override, everything lands next to the config
    assert main(["run", "-c", str(folder / "x.toml"), "--date", "2026-09-22", "--no-notify"]) == 0
    assert (folder / "site" / "out" / "index.html").exists()
    assert not (tmp_path / "site" / "out" / "index.html").exists()

    # with it, output lands where the publisher looks
    assert main(["run", "-c", str(folder / "x.toml"), "--date", "2026-09-23",
                 "--base-dir", str(tmp_path), "--no-notify"]) == 0
    assert (tmp_path / "site" / "out" / "index.html").exists()

    out = tmp_path / "index.html"
    assert main(["directory", "--out", str(out), "--base-dir", str(tmp_path), str(folder / "x.toml")]) == 0
    assert "worth opening" in out.read_text(encoding="utf-8")


def test_directory_reports_papers_read_not_what_the_last_run_judged(tmp_path):
    from paper_radar.cli import main

    cfg = tmp_path / "r.toml"
    cfg.write_text(
        f'[jev]\nbackend = "mock"\n'
        f'[[sources]]\ntype = "arxiv"\nfile = "{DEMO.as_posix()}"\n'
        '[[interests]]\nid = "agent_eval"\ntext = "Benchmarks for evaluating LLM agents"\n'
        f'[output]\nsite_dir = "{(tmp_path / "s").as_posix()}"\ndata_dir = "{(tmp_path / "d").as_posix()}"\n',
        encoding="utf-8",
    )
    assert main(["run", "-c", str(cfg), "--date", "2026-09-22", "--no-notify"]) == 0
    # a second run the same day judges nothing; the card must still say 44 were read
    assert main(["run", "-c", str(cfg), "--date", "2026-09-22", "--no-notify"]) == 0

    out = tmp_path / "index.html"
    assert main(["directory", "--out", str(out), str(cfg)]) == 0
    assert "<b>44</b> read" in out.read_text(encoding="utf-8")
