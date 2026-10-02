"""The news and social sources, and the duplicate folding they exist to feed."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from paper_radar.cluster import canonical_url, fold, jaccard, tokens
from paper_radar.models import Paper
from paper_radar.sources.bluesky import fetch_bluesky, parse_bluesky
from paper_radar.sources.reddit import fetch_reddit, parse_listing

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REDDIT = json.loads((FIXTURES / "reddit_top.json").read_text(encoding="utf-8"))
BLUESKY = json.loads((FIXTURES / "bluesky_feed.json").read_text(encoding="utf-8"))


# ── reddit ──────────────────────────────────────────────────────────────────────

def test_reddit_listing_maps_links_and_self_posts_differently():
    papers = parse_listing(REDDIT)
    by_id = {p.id: p for p in papers}

    assert "reddit:1ccccc" not in by_id, "a stickied mod thread is furniture, not news"
    assert all(not p.id.endswith("notapost") for p in papers), "only t3 children are posts"

    link = by_id["reddit:1aaaaa"]
    assert link.url == "https://openai.com/index/eval-suite/?utm_source=reddit"
    assert link.discussion == "https://www.reddit.com/r/singularity/comments/1aaaaa/openai_publishes_the_full_eval_suite/"
    # The domain is the strongest first-hand signal a bare link post has, so the model
    # has to be able to see it.
    assert "openai.com" in link.categories and "r/singularity" in link.categories
    assert "Posted as a link to openai.com." in link.abstract
    assert link.metrics == {"points": 2411, "comments": 318}

    self_post = by_id["reddit:1bbbbb"]
    assert self_post.url == self_post.discussion, "a self post has nothing else to point at"
    assert self_post.abstract == "I keep thinking about this and wanted to ask everyone what they expect."
    assert "self.singularity" not in " ".join(self_post.categories)


def test_reddit_floors_and_link_only_mode():
    assert {p.id for p in parse_listing(REDDIT, min_score=100)} == {"reddit:1aaaaa"}
    assert {p.id for p in parse_listing(REDDIT, min_comments=200)} == {"reddit:1aaaaa"}
    assert {p.id for p in parse_listing(REDDIT, require_link=True)} == {"reddit:1aaaaa", "reddit:1ddddd"}


def test_reddit_rejects_a_listing_it_cannot_honour(tmp_path):
    with pytest.raises(ValueError, match="listing must be one of"):
        fetch_reddit({"type": "reddit", "subreddits": ["x"], "listing": "best"}, getter=_boom, base_dir=tmp_path)
    with pytest.raises(ValueError, match="period must be one of"):
        fetch_reddit({"type": "reddit", "subreddits": ["x"], "period": "fortnight"}, getter=_boom, base_dir=tmp_path)


def test_reddit_asks_for_the_day_and_stays_inside_the_api_limit(tmp_path):
    calls: list[str] = []

    def getter(url: str) -> str:
        calls.append(url)
        return json.dumps(REDDIT)

    fetch_reddit(
        {"type": "reddit", "subreddits": ["singularity", "LocalLLaMA"], "limit": 500},
        getter=getter,
        base_dir=tmp_path,
    )
    assert len(calls) == 2
    assert "/r/singularity/top.json" in calls[0] and "t=day" in calls[0]
    assert "limit=100" in calls[0], "Reddit caps a listing at 100 and ignores more"


def _boom(url: str) -> str:  # pragma: no cover - the tests above must never fetch
    raise AssertionError(f"should not have fetched {url}")


# ── bluesky ─────────────────────────────────────────────────────────────────────

def test_bluesky_prefers_the_link_card_and_skips_reposts():
    papers = parse_bluesky(BLUESKY)
    assert len(papers) == 2, "the repost is the same item twice"

    first = papers[0]
    assert first.title == "Releasing the weights for Example-3"
    assert first.url == "https://blog.example.com/weights?utm_source=bluesky"
    assert first.discussion == "https://bsky.app/profile/lab.example.com/post/3mwqgsd4cgs2a"
    assert "Linked page: Weights, the eval harness" in first.abstract
    assert first.categories == ["@lab.example.com", "blog.example.com"]
    assert first.metrics == {"likes": 701, "reposts": 140, "replies": 15}

    # No card: the post's own text has to carry the title.
    assert papers[1].title == "Honestly the vibes this week are unreal"
    assert papers[1].url == "https://bsky.app/profile/someone.bsky.social/post/3mwolmfws5k2r"


def test_bluesky_filters():
    assert len(parse_bluesky(BLUESKY, min_likes=100)) == 1
    assert len(parse_bluesky(BLUESKY, require_link=True)) == 1
    assert len(parse_bluesky(BLUESKY, langs=["en"])) == 2
    assert len(parse_bluesky(BLUESKY, include_reposts=True)) == 3


def test_bluesky_ids_are_unique_across_authors():
    """The rkey is unique per repo, not globally: two authors can share one."""
    page = {
        "feed": [
            {"post": {"uri": f"at://did:plc:{who}/app.bsky.feed.post/3samerkey",
                      "author": {"handle": f"{who}.example.com"},
                      "record": {"text": f"post from {who}"}}}
            for who in ("aaa", "bbb")
        ]
    }
    assert len({p.id for p in parse_bluesky(page)}) == 2


def test_bluesky_says_plainly_that_search_needs_a_login(tmp_path):
    with pytest.raises(ValueError, match="needs a logged-in session"):
        fetch_bluesky({"type": "bluesky", "query": "openai"}, getter=_boom, base_dir=tmp_path)
    with pytest.raises(ValueError, match=r"needs `actors = "):
        fetch_bluesky({"type": "bluesky"}, getter=_boom, base_dir=tmp_path)


def test_bluesky_requests_one_feed_per_actor(tmp_path):
    calls: list[str] = []

    def getter(url: str) -> str:
        calls.append(url)
        return json.dumps(BLUESKY)

    fetch_bluesky({"type": "bluesky", "actors": ["a.example.com", "b.example.com"]}, getter=getter, base_dir=tmp_path)
    assert len(calls) == 2 and "actor=a.example.com" in calls[0]
    assert "filter=posts_no_replies" in calls[0]


# ── folding ─────────────────────────────────────────────────────────────────────

def test_canonical_url_ignores_what_does_not_change_the_page():
    same = {
        "https://www.example.com/a/b?utm_source=x&utm_campaign=y",
        "https://example.com/a/b/",
        "http://m.example.com/a/b?fbclid=123",
        "https://example.com/a/b/amp",
    }
    assert len({canonical_url(u) for u in same}) == 1
    assert canonical_url("https://example.com/a?id=7") != canonical_url("https://example.com/a?id=8")


def _item(title: str, url: str = "", source: str = "news", points: int = 0) -> Paper:
    return Paper(id=f"x:{title[:12]}{url}", source=source, title=title, abstract="", url=url,
                 metrics={"points": points} if points else {})


def test_fold_keeps_one_card_per_story():
    items = [
        _item("OpenAI releases Example-3 weights and eval harness", "https://openai.com/index/x/", points=10),
        _item("OpenAI releases Example-3 weights and the eval harness", "https://theverge.com/1"),
        _item("Example-3 weights released by OpenAI with eval harness", "https://arstechnica.com/2"),
        _item("Unrelated: a new router from a hardware vendor", "https://example.net/router"),
    ]
    folded = fold(items)
    assert len(folded) == 2
    story = folded[0]
    assert story.url == "https://openai.com/index/x/", "the most discussed copy survives"
    assert len(story.duplicates) == 2
    assert {d["source"] for d in story.duplicates} == {"news"}


def test_fold_merges_the_same_link_whatever_the_headline_says():
    """Two sites can retitle one announcement; the URL still says it is one story."""
    items = [
        _item("Totally different words here friend", "https://openai.com/index/x/?utm_source=a"),
        _item("Nothing alike about this headline", "https://www.openai.com/index/x"),
    ]
    assert len(fold(items)) == 1


def test_fold_leaves_short_headlines_alone():
    """"GPT-5 is out" and "GPT-6 is out" share most of their few tokens."""
    items = [_item("GPT-5 is out", "https://a.example/1"), _item("GPT-6 is out", "https://b.example/2")]
    assert len(fold(items)) == 2


def test_fold_is_idempotent_and_order_stable():
    items = [
        _item("A long enough headline about a specific announcement", "https://a.example/1", points=5),
        _item("A long enough headline about a specific announcement!", "https://b.example/2"),
        _item("Something else entirely, with different words in it", "https://c.example/3"),
    ]
    once = fold(items)
    assert [p.id for p in once] == [p.id for p in fold(list(once))]
    assert [p.title for p in once] == [items[0].title, items[2].title]


def test_tokens_and_jaccard_ignore_function_words():
    assert "the" not in tokens("The release of the model")
    assert jaccard(tokens("Model released by the lab"), tokens("Model released by a lab")) == 1.0


# ── what the page does with all of this ─────────────────────────────────────────

def test_a_news_card_shows_the_metrics_the_folding_and_the_discussion_link(tmp_path):
    from paper_radar.render import day_stats, render_day
    from paper_radar.scoring import Decision

    from .conftest import make_config

    config = make_config(tmp_path, thresholds={"must_read": 0.1, "maybe": 0.05, "exclude": 0.9})
    paper = Paper(
        id="reddit:1aaaaa",
        source="r/singularity",
        title="OpenAI publishes the eval suite behind its model card",
        abstract="Posted as a link to openai.com.",
        url="https://openai.com/index/eval-suite/",
        discussion="https://www.reddit.com/r/singularity/comments/1aaaaa/x/",
        metrics={"points": 2411, "comments": 1},
        duplicates=[{"title": "OpenAI publishes its eval suite", "url": "https://theverge.com/1", "source": "techmeme"}],
    )
    decision = Decision(paper=paper, relevance=0.9, band="must_read", interests={"agent_eval": 0.9}, exclusions={})
    page = render_day(config, "2026-10-02", [decision], day_stats("2026-10-02", [decision], []))

    assert "2,411 points · 1 comment" in page, "singular, and thousands separated"
    assert "Same story elsewhere (1)" in page and "theverge.com/1" in page
    assert 'class="discuss"' in page and "reddit.com/r/singularity/comments" in page


def test_the_pipeline_folds_before_judging(tmp_path):
    """Folding after judging would save nothing; the point is to pay once per story."""
    from paper_radar.jev import MockBackend
    from paper_radar.pipeline import run

    from .conftest import make_config

    feed = tmp_path / "news.xml"
    feed.write_text(
        '<rss version="2.0"><channel>'
        "<item><title>Example Lab releases the Example-3 weights today</title>"
        "<link>https://lab.example.com/weights</link><guid>a</guid></item>"
        "<item><title>Example Lab releases Example-3 weights today</title>"
        "<link>https://outlet.example.com/story</link><guid>b</guid></item>"
        "<item><title>A completely separate piece of hardware news arrives</title>"
        "<link>https://other.example.com/hw</link><guid>c</guid></item>"
        "</channel></rss>",
        encoding="utf-8",
    )
    source = [{"type": "rss", "name": "news", "url": "x", "file": str(feed)}]

    plain = run(make_config(tmp_path / "a", sources=source), MockBackend(), today=date(2026, 10, 2), notify=False, log=lambda _: None)
    folded = run(
        make_config(tmp_path / "b", sources=source, radar={"fold_duplicates": True}),
        MockBackend(), today=date(2026, 10, 2), notify=False, log=lambda _: None,
    )
    assert plain.judged == 3 and folded.judged == 2
    assert folded.tokens < plain.tokens, "a folded story is one judgement, not two"


def test_a_release_feed_borrows_the_project_name_for_its_terse_titles():
    """GitHub titles every release entry with the tag alone. "v0.30.0" is useless on the
    page and worse as the only text the model gets to judge."""
    from paper_radar.sources.rss import parse_feed

    atom = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><title>Release notes from llama.cpp</title>'
        '<entry><title>b11335</title><id>t1</id><link rel="alternate" href="https://e.org/1"/>'
        "<summary>Fixes</summary></entry>"
        "<entry><title>Something descriptive that must be left exactly as it is</title><id>t2</id>"
        '<link rel="alternate" href="https://e.org/2"/><summary>s</summary></entry></feed>'
    )
    titles = [p.title for p in parse_feed(atom, name="releases")]
    assert titles == ["llama.cpp b11335", "Something descriptive that must be left exactly as it is"]

    rss = (
        '<rss version="2.0"><channel><title>Releases - vllm</title>'
        "<item><title>v0.30.0</title><link>https://e.org/1</link><guid>g</guid></item></channel></rss>"
    )
    assert parse_feed(rss, name="releases")[0].title == "vllm v0.30.0"


def test_metric_labels_are_singular_properly():
    from paper_radar.render import _metric

    assert _metric("replies", 1) == "1 reply" and _metric("replies", 2) == "2 replies"
    assert _metric("points", 1) == "1 point" and _metric("comments", 2_411) == "2,411 comments"


def test_rejudge_judges_todays_items_again(tmp_path):
    """Change the criteria and rerun, and without this the dedupe window means nothing
    is judged: the page keeps showing verdicts the old config produced."""
    from paper_radar.jev import MockBackend
    from paper_radar.pipeline import run
    from paper_radar.store import Store

    from .conftest import make_config

    config = make_config(tmp_path)
    first = run(config, MockBackend(), today=date(2026, 10, 2), notify=False, log=lambda _: None)
    assert first.judged == 44

    again = run(config, MockBackend(), today=date(2026, 10, 2), notify=False, log=lambda _: None)
    assert again.judged == 0, "the dedupe window is doing its normal job"

    fresh = run(config, MockBackend(), today=date(2026, 10, 2), notify=False, rejudge=True, log=lambda _: None)
    assert fresh.judged == 44
    # and the day's file is replaced, not appended to twice over
    assert len(Store(config.data_path).load_decisions("2026-10-02")) == 44
