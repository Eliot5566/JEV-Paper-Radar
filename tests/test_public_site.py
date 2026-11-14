"""The promotional page must coexist with saved public feeds without API calls."""

from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import shutil
import socket
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from paper_radar.models import Paper
from paper_radar.scoring import Decision
from paper_radar.store import Store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_builder", ROOT / "scripts/build_public_site.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.targets.append(value)


def test_offline_rebuild_preserves_feeds_and_adds_working_showcase(tmp_path, monkeypatch):
    for name in ("radar.toml", "radar.public.toml"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "radars", tmp_path / "radars")
    shutil.copytree(ROOT / "showcase", tmp_path / "showcase")
    for directory, identity, title in [("data", "fixture:mine", "Saved personal decision"),
                                       ("data/public", "fixture:public", "Saved public decision")]:
        paper = Paper(id=identity, source="fixture", title=title, abstract="Saved abstract", url="https://example.org/paper")
        Store(tmp_path / directory).write_decisions("2026-11-13", [Decision(paper, 0.95, "must_read", {}, {})])
    def blocked(*args, **kwargs):
        raise AssertionError("site publication must not make network calls")
    monkeypatch.setattr(socket, "create_connection", blocked)
    counts = builder.build(tmp_path)
    assert counts["mine"] == 1 and counts["radar.public.toml"] == 1
    site = tmp_path / "site"
    assert "Saved personal decision" in (site / "mine/index.html").read_text(encoding="utf-8")
    assert "Saved public decision" in (site / "public/ai/index.html").read_text(encoding="utf-8")
    assert (site / "public/index.html").is_file() and (site / "index.html").is_file()
    for html_file in (site / "try").rglob("*.html"):
        parser = Links()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for target in parser.targets:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = (html_file.parent / unquote(parsed.path)).resolve()
            assert path.is_relative_to(site), target
            if parsed.path.endswith("/"):
                path = path / "index.html"
            assert path.is_file(), (html_file.relative_to(site), target)
    for filename in ("try/demo/feed.xml", "try/report/feed.xml", "try/real/feed.xml", "public/ai/feed.xml"):
        ET.parse(site / filename)
    example = json.loads((site / "try/report/report.json").read_text(encoding="utf-8"))
    assert example["input_kind"] == "fictional"
    assert len(example["papers"]) == 3
    assert example["cost_usd"] is None
    real = json.loads((site / "try/real/report.json").read_text(encoding="utf-8"))
    assert real["input_kind"] == "retrieved"
    assert {p["id"] for p in real["papers"]} == {"arxiv:2308.03688", "arxiv:2302.04761"}
    assert all(p["abstract_kind"] == "web-summary" for p in real["papers"])
    assert real["retrieval"]["errors"] and real["cost_usd"] is None


def test_public_output_cannot_escape_site_directory(tmp_path):
    shutil.copyfile(ROOT / "radar.toml", tmp_path / "radar.toml")
    config = (ROOT / "radar.public.toml").read_text(encoding="utf-8")
    (tmp_path / "radar.public.toml").write_text(config.replace('site_dir = "site/public/ai"', 'site_dir = "../outside"'), encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="inside site"):
        builder.build(tmp_path)
