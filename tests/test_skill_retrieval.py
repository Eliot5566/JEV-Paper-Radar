"""Public retrieval must preserve evidence, omissions and network boundaries."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "skills/paper-radar/scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load("skill_retrieval", "retrieve.py")
exporter = load("retrieved_exporter", "chat_report.py")
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
ATOM = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/2308.03688v1</id><title>Agent evaluation fixture</title>
<summary>A fictional fixture about evaluation; not real paper text.</summary>
<published>2023-08-07T00:00:00Z</published></entry></feed>'''
PUBMED = '''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1234</PMID>
<Article><ArticleTitle>Memory <i>study</i></ArticleTitle><Abstract>
<AbstractText Label="METHODS">A controlled <i>fixture</i>.</AbstractText>
<AbstractText Label="RESULTS">Fictional outcome.</AbstractText></Abstract></Article>
</MedlineCitation></PubmedArticle></PubmedArticleSet>'''


class Fake:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def get(self, url):
        assert r.allowed_endpoint(url), url
        self.requests.append({"url": url, "status": "ok"})
        result = next(self.responses)
        if isinstance(result, Exception):
            self.requests[-1]["status"] = "failed"
            raise result
        return result


@pytest.mark.parametrize("value,expected", [
    ("https://arxiv.org/pdf/2308.03688.pdf?download=1", ("arxiv", "2308.03688")),
    ("https://arxiv.org/html/2308.03688v2", ("arxiv", "2308.03688v2")),
    ("arXiv:hep-th/9901001", ("arxiv", "hep-th/9901001")),
    ("https://arxiv.org/abs/cs.AI/9901001", ("arxiv", "cs.AI/9901001")),
    ("https://pubmed.ncbi.nlm.nih.gov/1234/", ("pubmed", "1234")),
    ("PMID:1234", ("pubmed", "1234")),
    ("https://doi.org/10.1234/ABC", ("crossref", "10.1234/abc")),
    ("doi:10.1234/a(b)", ("crossref", "10.1234/a(b)")),
])
def test_supported_identifiers(value, expected):
    assert r.identify(value) == expected


@pytest.mark.parametrize("value", ["file:///etc/passwd", "http://127.0.0.1/paper", "https://arxiv.org.evil.test/abs/2308.03688",
    "https://user:pass@arxiv.org/abs/2308.03688", "https://arxiv.org:8888/abs/2308.03688",
    "https://example.org/paper.pdf", "https://arxiv.org/abs/not-an-id", "javascript:alert(1)"])
def test_unsupported_links_never_cause_requests(value):
    fake = Fake()
    result = r.retrieve(links=[value], client=fake, now=NOW)
    assert not result["papers"] and result["retrieval"]["errors"]
    assert not fake.requests


def test_link_resolution_deduplicates_versions_preserves_provenance_and_reports_missing(tmp_path):
    fake = Fake(ATOM, PUBMED.replace("<Abstract>", "<Other>").replace("</Abstract>", "</Other>"))
    result = r.retrieve(links=["arxiv:2308.03688", "arxiv:2308.03688v1", "pmid:1234", "pmid:9876"], limit=1, client=fake, now=NOW)
    assert len(result["papers"]) == 1
    paper = result["papers"][0]
    assert paper["id"] == "arxiv:2308.03688v1" and paper["retrieved_at"] == NOW.isoformat()
    assert paper["metadata_url"].startswith(r.ARXIV)
    assert len(result["retrieval"]["missing_abstracts"]) == 1
    assert any(x["input"] == "pubmed:9876" for x in result["retrieval"]["errors"])
    assert result["retrieval"]["status"] == "partial"
    r.write_result(result, tmp_path / "retrieved")
    assert json.loads((tmp_path / "retrieved/papers.json").read_text())["papers"] == result["papers"]
    with pytest.raises(ValueError, match="empty output"):
        r.write_result(result, tmp_path / "retrieved")


def test_arxiv_query_has_explicit_utc_window_and_bounded_candidates():
    fake = Fake(ATOM)
    result = r.retrieve(query='all:"agent evaluation"', days=7, limit=3, client=fake, now=NOW)
    params = parse_qs(urlsplit(fake.requests[0]["url"]).query)
    assert "submittedDate:[202611070000 TO 202611142359]" in params["search_query"][0]
    assert params["max_results"] == ["3"]
    assert result["retrieval"]["query"] == 'all:"agent evaluation"'
    assert result["retrieval"]["model_api_requests"] == 0


def test_pubmed_search_to_abstracts_keeps_sections_and_inline_text():
    fake = Fake(json.dumps({"esearchresult": {"idlist": ["1234"]}}), PUBMED)
    result = r.retrieve(query="sleep memory", source="pubmed", client=fake, now=NOW)
    assert len(fake.requests) == 2
    assert "datetype=edat" in fake.requests[0]["url"]
    paper = result["papers"][0]
    assert paper["title"] == "Memory study"
    assert paper["abstract"] == "METHODS: A controlled fixture.\nRESULTS: Fictional outcome."


def test_crossref_missing_abstract_is_manual_review_not_scored():
    raw = json.dumps({"message": {"DOI": "10.1234/abc", "title": ["A real identifier fixture"]}})
    result = r.retrieve(links=["https://doi.org/10.1234/ABC"], client=Fake(raw), now=NOW)
    assert not result["papers"]
    assert result["retrieval"]["missing_abstracts"][0]["id"] == "doi:10.1234/abc"
    assert result["retrieval"]["status"] == "empty"
    with pytest.raises(ValueError, match="different DOI"):
        r.parse_crossref(raw, "10.1234/different")
    row = r.parse_crossref(raw.replace('"title":', '"abstract":"<jats:p>A <b>study</b>.</jats:p>","title":'), "10.1234/abc")[0]
    assert row["abstract"] == "A study ."


def test_unavailable_source_partial_and_empty_results_are_explicit():
    result = r.retrieve(links=["arxiv:2308.03688", "pmid:1234"], client=Fake(ValueError("blocked"), PUBMED), now=NOW)
    assert result["retrieval"]["status"] == "partial" and len(result["papers"]) == 1
    assert result["retrieval"]["errors"][0]["error"] == "blocked"
    result = r.retrieve(query="missing", client=Fake('<feed xmlns="http://www.w3.org/2005/Atom"/>'), now=NOW)
    assert result["retrieval"]["status"] == "empty" and not result["papers"]
    result = r.retrieve(query="bad", client=Fake("not xml"), now=NOW)
    assert result["retrieval"]["status"] == "failed"


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 21}, {"limit": True}, {"days": -1}, {"days": 3651},
                                        {"days": False}, {"query": " "}, {"source": "unknown"}])
def test_invalid_search_bounds_before_network(kwargs):
    fake = Fake()
    args = {"query": "agents", "client": fake, **kwargs}
    with pytest.raises(ValueError):
        r.retrieve(**args)
    assert not fake.requests


def test_network_transport_limits_endpoint_redirect_size_and_rate(monkeypatch):
    waits = []
    monkeypatch.setattr(r.time, "sleep", waits.append)
    monkeypatch.setattr(r.time, "monotonic", lambda: 1)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def geturl(self): return r.ARXIV
        def read(self, n): return b"<feed/>"
    class Opener:
        def open(self, req, timeout): return Response()
    client = r.Client()
    client.opener = Opener()
    assert client.get(r.ARXIV) == "<feed/>"
    client.get(r.ARXIV)
    assert waits[-1] == 3.1
    with pytest.raises(ValueError, match="unsupported"):
        client.get("https://127.0.0.1/secret")
    with pytest.raises(ValueError, match="redirect"):
        r.RestrictedRedirect().redirect_request(None, None, 302, "", {}, "https://example.org/")
    monkeypatch.setattr(Response, "read", lambda self, n: b"x" * (r.MAX_BYTES + 1))
    with pytest.raises(ValueError, match="2 MB"):
        client.get(r.ARXIV)
    assert client.requests[-1]["status"] == "failed"


def test_retrieved_report_preserves_audit_and_every_scored_id(tmp_path):
    result = r.retrieve(links=["arxiv:2308.03688", "https://example.org/paper"], client=Fake(ATOM), now=NOW)
    result.update(title="Retrieved example", interest="Agent evaluation")
    result["papers"][0].update(score=0.9, reason="Fixture includes agent evaluation.")
    report = exporter.render(result, tmp_path / "report")
    assert report["retrieval"] == result["retrieval"]
    assert report["papers"][0]["metadata_url"] == result["papers"][0]["metadata_url"]
    assert report["token_usage"] is None and report["cost_usd"] is None
    page = (tmp_path / "report/index.html").read_text()
    assert "Retrieved public metadata" in page and "1 errors" in page
    assert len(ET.parse(tmp_path / "report/feed.xml").findall("./channel/item")) == 1
    del result["retrieval"]
    with pytest.raises(ValueError, match="retrieval audit"):
        exporter.validate(result)
