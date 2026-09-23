import json
from datetime import date

from paper_radar.sources import collect
from paper_radar.sources.arxiv import ALL_ARCHIVES, feed_url, parse_arxiv_rss
from paper_radar.sources.biorxiv import fetch_biorxiv, parse_biorxiv
from paper_radar.sources.rss import parse_feed

from .conftest import DEMO_FEED

ARXIV_SNIPPET = """<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0"><channel>
<item><title>A New Paper</title><link>https://arxiv.org/abs/2609.01234</link>
<description>arXiv:2609.01234v1 Announce Type: new
Abstract: We do   things.
Across lines.</description>
<category>cs.CL</category><category>cs.AI</category>
<arxiv:announce_type>new</arxiv:announce_type><dc:creator>Ada Lovelace, Alan Turing and Grace Hopper</dc:creator></item>
<item><title>Cross Listed</title><link>https://arxiv.org/abs/2609.05678</link>
<description>arXiv:2609.05678v1 Announce Type: cross
Abstract: Cross.</description><arxiv:announce_type>cross</arxiv:announce_type></item>
<item><title>Revised</title><link>https://arxiv.org/abs/2501.00001</link>
<description>arXiv:2501.00001v3 Announce Type: replace
Abstract: Old.</description><arxiv:announce_type>replace</arxiv:announce_type></item>
<item><title>Old style id</title><link>https://arxiv.org/abs/hep-th/9901001v2</link>
<description>no id in text</description><arxiv:announce_type>new</arxiv:announce_type></item>
</channel></rss>"""


def test_parse_arxiv_basic():
    papers = parse_arxiv_rss(ARXIV_SNIPPET)
    ids = [p.id for p in papers]
    assert ids == ["arxiv:2609.01234", "arxiv:2609.05678", "arxiv:hep-th/9901001"]
    first = papers[0]
    assert first.abstract == "We do things. Across lines."
    assert first.authors == ["Ada Lovelace", "Alan Turing", "Grace Hopper"]
    assert first.categories == ["cs.CL", "cs.AI"]
    assert first.announce_type == "new"


def test_parse_arxiv_filters():
    assert len(parse_arxiv_rss(ARXIV_SNIPPET, include_cross=False)) == 2
    assert len(parse_arxiv_rss(ARXIV_SNIPPET, include_replacements=True)) == 4


def test_feed_url():
    assert feed_url(["cs.AI", "cs.CL"]) == "https://rss.arxiv.org/rss/cs.AI+cs.CL"
    assert feed_url(["*"]).endswith("+".join(ALL_ARCHIVES))


def test_demo_feed_parses():
    papers = parse_arxiv_rss(DEMO_FEED.read_text())
    assert len(papers) >= 40
    assert all(p.id.startswith("arxiv:2609.99") for p in papers)
    assert not any("Revised Today" in p.title for p in papers)


def _page(records, total):
    return {"messages": [{"status": "ok", "total": str(total)}], "collection": records}


def _rec(doi, version="1", category="neuroscience"):
    return {"doi": doi, "title": f"T {doi}", "authors": "A; B", "abstract": "abs", "version": version,
            "category": category, "date": "2026-09-21", "server": "bioRxiv"}


def test_biorxiv_parse_and_filter():
    page = _page([_rec("10.1101/1"), _rec("10.1101/2", version="2"), _rec("10.1101/3", category="cell biology")], 3)
    papers = parse_biorxiv(page, server="biorxiv", wanted={"cell_biology"})
    assert [p.id for p in papers] == ["biorxiv:10.1101/3"]
    assert papers[0].url == "https://www.biorxiv.org/content/10.1101/3v1"
    assert papers[0].authors == ["A", "B"]


def test_biorxiv_pagination(tmp_path):
    calls = []

    def getter(url):
        calls.append(url)
        cursor = int(url.rsplit("/", 1)[1])
        records = [_rec(f"10.1101/{cursor + i}") for i in range(100 if cursor == 0 else 50)]
        return json.dumps(_page(records, 150))

    papers = fetch_biorxiv({"type": "biorxiv"}, getter=getter, base_dir=tmp_path, today=date(2026, 9, 22))
    assert len(papers) == 150
    assert calls[0] == "https://api.biorxiv.org/details/biorxiv/2026-09-21/2026-09-22/0"
    assert calls[1].endswith("/100")


def test_rss_and_atom():
    rss = """<rss version="2.0"><channel><item><title>Hello &lt;b&gt;x&lt;/b&gt;</title><link>https://e.org/1</link>
    <description>&lt;p&gt;Body &amp;amp; more&lt;/p&gt;</description><guid>g1</guid></item></channel></rss>"""
    items = parse_feed(rss, name="blog")
    assert items[0].title == "Hello x" and items[0].abstract == "Body & more" and items[0].id.startswith("rss:")
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><id>tag:1</id>
    <link rel="self" href="https://e.org/self"/><link rel="alternate" href="https://e.org/a"/>
    <summary>S</summary><author><name>N</name></author></entry></feed>"""
    entries = parse_feed(atom, name="atom")
    assert entries[0].url == "https://e.org/a" and entries[0].authors == ["N"]


def test_collect_dedupes_and_survives_broken_source(tmp_path):
    logs = []
    sources = [
        {"type": "arxiv", "file": str(DEMO_FEED)},
        {"type": "arxiv", "file": str(DEMO_FEED)},
        {"type": "rss", "name": "broken", "url": "https://example.invalid/feed"},
    ]

    def getter(url):
        raise OSError("boom")

    papers = collect(sources, today=date(2026, 9, 22), base_dir=tmp_path, getter=getter, log=logs.append)
    assert len(papers) == len({p.id for p in papers})
    assert any("broken failed" in line for line in logs)
