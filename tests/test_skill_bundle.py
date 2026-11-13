"""Installable bundle: no site packages, network dependency, or missing fixtures."""

from copy import deepcopy
import hashlib
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_script("skill_builder", ROOT / "scripts/build_claude_skill.py")
exporter = load_script("chat_exporter", ROOT / "skills/paper-radar/scripts/chat_report.py")


def report_input():
    return {"title": "Test report", "interest": "Tool-using agent benchmarks", "input_kind": "fictional",
            "papers": [{"id": "sample:1", "title": "A benchmark", "abstract": "A benchmark for tool use.",
                        "url": "https://example.org/paper", "score": 0.9, "reason": "Introduces a tool-use benchmark."},
                       {"id": "sample:2", "title": "A tomato", "abstract": "Tomato leaf images.",
                        "url": "", "score": 0.1, "reason": "Image classification rather than agents."}]}


def test_archive_is_complete_and_reproducible(tmp_path):
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    info = builder.build(a, "test-commit")
    builder.build(b, "test-commit")
    assert a.read_bytes() == b.read_bytes()
    assert 1 <= info["description_characters"] <= 200
    with zipfile.ZipFile(a) as archive:
        names = archive.namelist()
        assert all(name.startswith("paper-radar/") and ".." not in Path(name).parts for name in names)
        assert not any(name.endswith((".pyc", ".env")) or "__pycache__" in name for name in names)
        manifest = json.loads(archive.read("paper-radar/bundle-manifest.json"))
        assert manifest["source_commit"] == "test-commit"
        assert manifest["external_runtime_dependencies"] == []
        assert set(names) == {"paper-radar/" + name for name in manifest["files"]} | {"paper-radar/bundle-manifest.json"}
        for path, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read("paper-radar/" + path)).hexdigest() == digest
        archive.extractall(tmp_path / "installed")
    wrapper = tmp_path / "installed/paper-radar/scripts/run.py"
    # Ignore installed site packages. Block HTTP connections in the isolated child.
    guard = "import socket,runpy,sys; socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('network disabled')); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    demo = tmp_path / "demo"
    result = subprocess.run([sys.executable, "-I", "-S", "-c", guard, str(wrapper), "demo", "--out", str(demo)],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stderr
    assert (demo / "site/index.html").is_file()
    ET.parse(demo / "site/feed.xml")
    decisions = list((demo / "data/decisions").glob("*.jsonl"))
    total = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in decisions)
    for path in (demo / "data/decisions").glob("*.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            total += len(handle.read().splitlines())
    assert total == 44
    assert "fictional" in (demo / "site/index.html").read_text(encoding="utf-8")
    check = subprocess.run([sys.executable, "-I", "-S", str(wrapper), "check", "-c",
                            str(wrapper.parents[1] / "references/claude-starter.toml")],
                           cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert check.returncode == 0, check.stderr


@pytest.mark.parametrize("bad", [True, None, -0.01, 1.01, float("nan"), float("inf"), "0.9", 10 ** 400])
def test_invalid_chat_scores_are_rejected_before_writing(tmp_path, bad):
    data = report_input()
    data["papers"][0]["score"] = bad
    out = tmp_path / "bad"
    with pytest.raises(ValueError):
        exporter.render(data, out)
    assert not out.exists()


def test_chat_export_preserves_low_scores_provenance_and_safe_output(tmp_path):
    data = report_input()
    data["papers"][0]["title"] = '=HYPERLINK("https://example.org")'
    data["papers"][0]["reason"] = '<script>alert("x")</script>'
    data["papers"][1]["score"] = 0.95
    out = tmp_path / "report"
    report = exporter.render(data, out)
    assert [p["id"] for p in report["papers"]] == ["sample:2", "sample:1"]
    assert report["token_usage"] is None and report["cost_usd"] is None
    assert report["external_api_requests_by_renderer"] == 0
    assert len(ET.parse(out / "feed.xml").findall("./channel/item")) == 2
    assert "<script>" not in (out / "index.html").read_text()
    assert "&lt;script&gt;" in (out / "index.html").read_text()
    assert "'=HYPERLINK" in (out / "report.csv").read_text(encoding="utf-8-sig")
    with pytest.raises(ValueError, match="empty output"):
        exporter.render(data, out)
    data["papers"][1]["score"] = 0.1
    exporter.render(data, tmp_path / "with-skip")
    assert len(ET.parse(tmp_path / "with-skip/feed.xml").findall("./channel/item")) == 1


@pytest.mark.parametrize("change", ["duplicate", "unsafe_url", "thresholds", "missing_abstract"])
def test_bad_chat_records_are_rejected(change):
    data = deepcopy(report_input())
    if change == "duplicate":
        data["papers"][1]["id"] = data["papers"][0]["id"]
    elif change == "unsafe_url":
        data["papers"][0]["url"] = "javascript:alert(1)"
    elif change == "thresholds":
        data["thresholds"] = {"must_read": 0.2, "maybe": 0.8}
    else:
        del data["papers"][0]["abstract"]
    with pytest.raises(ValueError):
        exporter.validate(data)
