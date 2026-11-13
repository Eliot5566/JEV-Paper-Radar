"""Render scores made in the current conversation; no network or API calls."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def score(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number in [0, 1]")
    if not 0 <= value <= 1 or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number in [0, 1]")
    return float(value)


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("report must be a JSON object")
    title = text(data.get("title"), "title")
    interest = text(data.get("interest"), "interest")
    kind = data.get("input_kind")
    if kind not in ("fictional", "user-provided"):
        raise ValueError("input_kind must be fictional or user-provided")
    thresholds = data.get("thresholds", {"must_read": 0.8, "maybe": 0.5})
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds must be an object")
    must = score(thresholds.get("must_read"), "must_read")
    maybe = score(thresholds.get("maybe"), "maybe")
    if maybe > must:
        raise ValueError("maybe threshold cannot exceed must_read")
    papers = data.get("papers")
    if not isinstance(papers, list) or not 1 <= len(papers) <= 200:
        raise ValueError("papers must contain 1 to 200 records")
    rows, ids = [], set()
    for index, paper in enumerate(papers):
        if not isinstance(paper, dict):
            raise ValueError(f"paper {index} must be an object")
        row = {key: text(paper.get(key), f"paper {index} {key}")
               for key in ("id", "title", "abstract", "reason")}
        if row["id"] in ids:
            raise ValueError(f"duplicate paper id: {row['id']}")
        ids.add(row["id"])
        url = paper.get("url", "")
        if not isinstance(url, str):
            raise ValueError("url must be a string")
        if url and (urlsplit(url).scheme.lower() not in ("http", "https") or not urlsplit(url).netloc
                    or any(c.isspace() for c in url)):
            raise ValueError("paper URL must be an absolute http(s) URL or empty")
        row["url"] = url
        row["score"] = score(paper.get("score"), f"paper {index} score")
        row["band"] = "must_read" if row["score"] >= must else "maybe" if row["score"] >= maybe else "skip"
        rows.append(row)
    return {"title": title, "interest": interest, "input_kind": kind,
            "thresholds": {"must_read": must, "maybe": maybe},
            "scorer": "Claude conversation (self-reported scores)",
            "token_usage": None, "cost_usd": None,
            "external_api_requests_by_renderer": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "papers": sorted(rows, key=lambda row: row["score"], reverse=True)}


def csv_cell(value):
    # Paper text is untrusted and CSV files may be opened in spreadsheet apps.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def render(data, out):
    report = validate(data)
    out = Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("choose a new or empty output directory")
    out.mkdir(parents=True, exist_ok=True)
    e = html.escape
    notice = ("Fictional input. " if report["input_kind"] == "fictional" else "User-provided abstracts. ")
    notice += ("Scores were made in the current Claude conversation and are not calibrated probabilities. "
               "Chat usage and cost are unavailable to this report. This renderer made no API requests.")
    cards = []
    for row in report["papers"]:
        heading = e(row["title"])
        if row["url"]:
            heading = f'<a href="{e(row["url"], quote=True)}">{heading}</a>'
        cards.append(f'<article><small>{e(row["band"])} · {row["score"]:.2f}</small>'
                     f'<h2>{heading}</h2><p>{e(row["reason"])}</p>'
                     f'<details><summary>Abstract</summary><p>{e(row["abstract"])}</p></details></article>')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(report["title"])}</title>'
            '<style>body{font:16px/1.6 system-ui;max-width:850px;margin:32px auto;padding:0 20px;'
            'background:#f6f6f3;color:#1a1b1e}article,aside{padding:20px;margin:18px 0;border:1px solid #ddd;'
            'border-radius:12px;background:white}aside{background:#fff7df}a{color:#2563eb}h2{font-size:20px}</style>'
            f'<h1>{e(report["title"])}</h1><p>Interest: {e(report["interest"])}</p>'
            f'<aside>{e(notice)}</aside>{"".join(cards)}'
            '<footer>Paper Radar · Claude conversation report</footer></html>')
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (out / "report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        fields = ["id", "title", "score", "band", "reason", "url", "abstract"]
        writer.writerow(fields)
        writer.writerows([csv_cell(row[key]) for key in fields] for row in report["papers"])
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = report["title"]
    ET.SubElement(channel, "link").text = "https://github.com/Eliot5566/JEV-Paper-Radar"
    ET.SubElement(channel, "description").text = notice + " Interest: " + report["interest"]
    for row in report["papers"]:
        if row["band"] == "skip":
            continue
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = row["title"]
        ET.SubElement(item, "guid", isPermaLink="false").text = row["id"]
        if row["url"]:
            ET.SubElement(item, "link").text = row["url"]
        # RSS readers commonly interpret description as HTML.
        ET.SubElement(item, "description").text = e(row["reason"])
    ET.ElementTree(rss).write(out / "feed.xml", encoding="utf-8", xml_declaration=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON containing user-provided abstracts and Claude conversation scores")
    parser.add_argument("--out", required=True, help="a new or empty output directory")
    args = parser.parse_args()
    try:
        report = render(json.loads(Path(args.input).read_text(encoding="utf-8")), args.out)
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps({"papers": len(report["papers"]), "output": str(Path(args.out).resolve()),
                      "api_requests_by_renderer": 0, "usage_and_cost": "unavailable"}))


if __name__ == "__main__":
    main()
