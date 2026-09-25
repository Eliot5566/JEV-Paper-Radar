"""Static site (GitHub Pages) and RSS feed. Self-contained HTML, no JS, light + dark."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from . import REPO_URL, __version__
from .config import Config
from .feedback import issue_url
from .questions import PAPER_TYPES
from .scoring import Decision, rank

TYPE_LABELS = {k: k.replace("_", " ") for k in PAPER_TYPES}

CSS = """
:root{--bg:#f6f6f3;--surface:#fff;--text:#1a1b1e;--muted:#5d6168;--border:#e2e2dc;--accent:#2563eb;
--must:#0b7a53;--must-bg:#e6f4ee;--maybe:#9a6412;--maybe-bg:#fbf1e1;--chip:#eef1f8;--track:#e3e6ee;--warn-bg:#fff7e0;--warn:#7a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#0e1014;--surface:#161a21;--text:#e7e9ec;--muted:#9aa0a8;--border:#2a303b;
--accent:#7ea6ff;--must:#44c99a;--must-bg:#12281f;--maybe:#e3ad55;--maybe-bg:#2b2112;--chip:#1e2430;--track:#2a3140;--warn-bg:#2b250f;--warn:#e9cf7a}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans TC","PingFang TC",sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:820px;margin:0 auto;padding:0 16px}
header.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 0 8px}
.brand{display:flex;align-items:center;gap:10px;font-weight:650;letter-spacing:-.01em}
.brand svg{width:26px;height:26px;color:var(--accent)}
nav a{margin-left:14px;font-size:14px;color:var(--muted)}
.hero{padding:18px 0 8px}
.hero h1{font-size:28px;line-height:1.2;margin:0 0 4px;letter-spacing:-.02em}
.hero p.sub{margin:0;color:var(--muted)}
.funnel{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;align-items:center;gap:8px;margin:18px 0 10px}
.stage{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.stage b{display:block;font-size:26px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.stage span{font-size:13px;color:var(--muted)}
.stage.must{border-color:var(--must);background:var(--must-bg)}.stage.must b{color:var(--must)}
.arrow{color:var(--muted);font-size:18px}
.meta{font-size:13px;color:var(--muted);margin:0 0 6px;font-variant-numeric:tabular-nums}
.banner{background:var(--warn-bg);color:var(--warn);border-radius:10px;padding:10px 12px;font-size:14px;margin:12px 0}
.banner .why{display:block;margin-top:4px;font-size:12.5px;opacity:.8;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
h2{font-size:18px;margin:28px 0 10px;display:flex;align-items:baseline;gap:8px}
h2 small{font-weight:400;color:var(--muted);font-size:14px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px;margin:10px 0}
.card.must_read{border-left:4px solid var(--must)}.card.maybe{border-left:4px solid var(--maybe)}
.row{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:12.5px}
.pct{font-weight:700;font-variant-numeric:tabular-nums;font-size:13px;padding:2px 8px;border-radius:999px}
.must_read .pct{background:var(--must-bg);color:var(--must)}.maybe .pct{background:var(--maybe-bg);color:var(--maybe)}
.tag{background:var(--chip);border-radius:999px;padding:2px 8px;color:var(--muted)}
.card h3{font-size:16.5px;line-height:1.35;margin:8px 0 4px;letter-spacing:-.01em}
.by{margin:0;color:var(--muted);font-size:13px}
.tldr{margin:8px 0 0;font-size:14.5px}
.why{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.why .chip{display:inline-flex;align-items:center;gap:6px;background:var(--chip);border-radius:8px;padding:3px 8px;font-size:12.5px}
.meter{width:44px;height:6px;border-radius:3px;background:var(--track);overflow:hidden}
.meter i{display:block;height:100%;background:var(--accent)}
details{margin-top:8px}summary{cursor:pointer;color:var(--muted);font-size:13px}
details p{font-size:14px;margin:6px 0 0}
.id{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px;color:var(--muted)}
.foot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:10px;flex-wrap:wrap}
.vote{font-size:12.5px;color:var(--muted)}
.vote a{display:inline-block;border:1px solid var(--border);border-radius:8px;padding:1px 8px;margin-left:6px;text-decoration:none}
.vote a:hover{border-color:var(--accent);text-decoration:none}
.list{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:4px 14px;margin:10px 0}
.list li{list-style:none;padding:8px 0;border-bottom:1px solid var(--border);font-size:14px}
.list li:last-child{border-bottom:0}.list ul{margin:0;padding:0}
.list .pct{background:var(--chip);color:var(--muted);margin-right:6px}
.empty{color:var(--muted);font-size:14px;padding:6px 0}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums;background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border)}th{color:var(--muted);font-weight:500}
footer{color:var(--muted);font-size:13px;padding:28px 0 40px}
footer code{font-size:12px}
@media (max-width:560px){.funnel{grid-template-columns:1fr 1fr 1fr}.arrow{display:none}.stage b{font-size:22px}.hero h1{font-size:24px}}
"""

LOGO = (
    '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
    '<circle cx="16" cy="16" r="13" opacity=".35"/><circle cx="16" cy="16" r="8" opacity=".6"/>'
    '<circle cx="16" cy="16" r="2.5" fill="currentColor"/><path d="M16 16 L26 7" stroke-linecap="round"/></svg>'
)


def _e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def _url(value: str) -> str:
    """Only http(s) links reach an href; feeds are untrusted input."""
    return _e(value) if str(value).lower().startswith(("http://", "https://")) else "#"


def _pct(value: float) -> str:
    return f"{round(value * 100)}%"


def _num(value: int) -> str:
    return f"{value:,}"


def _authors(authors: list[str]) -> str:
    if not authors:
        return ""
    return ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")


def day_stats(day: str, decisions: list[Decision], runs: list[dict[str, Any]]) -> dict[str, Any]:
    day_runs = [r for r in runs if r.get("day") == day]
    counts = {band: sum(1 for d in decisions if d.band == band) for band in ("must_read", "maybe", "excluded")}
    # From the run record, not from this process, so a rebuild keeps saying which source
    # was down on the day it was down.
    failed: dict[str, str] = {}
    for run in day_runs:
        for failure in run.get("source_failures") or []:
            failed[str(failure.get("source") or "?")] = str(failure.get("error") or "")
    return {
        "judged": len(decisions),
        "source_failures": [{"source": k, "error": v} for k, v in failed.items()],
        **counts,
        "tokens": sum(d.input_tokens for d in decisions),
        "cost": sum(d.cost for d in decisions),
        "seconds": sum(float(r.get("seconds") or 0) for r in day_runs),
        "fetched": sum(int(r.get("fetched") or 0) for r in day_runs),
        "backend": (day_runs[-1].get("backend") if day_runs else "") or "",
        "model": (day_runs[-1].get("model") if day_runs else "") or (decisions[0].model if decisions else ""),
    }


def _votes(d: Decision, feedback_repo: str) -> str:
    """Two links that open a pre-filled GitHub issue; `paper-radar harvest` turns them into labels."""
    if not feedback_repo:
        return ""
    p = d.paper
    yes = issue_url(feedback_repo, p.id, p.title, p.url, "yes")
    no = issue_url(feedback_repo, p.id, p.title, p.url, "no")
    return (
        f'<span class="vote">Useful?<a href="{_e(yes)}" title="Record this paper as relevant">👍</a>'
        f'<a href="{_e(no)}" title="Record this paper as not relevant">👎</a></span>'
    )


def _card(d: Decision, labels: dict[str, str], feedback_repo: str = "") -> str:
    p = d.paper
    tags = [f'<span class="pct">{_pct(d.relevance)}</span>']
    if d.paper_type:
        tags.append(f'<span class="tag">{_e(TYPE_LABELS.get(d.paper_type, d.paper_type))}</span>')
    if d.code is not None and d.code >= 0.6:
        tags.append('<span class="tag">code / data</span>')
    tags.append(f'<span class="tag">{_e(p.source)}</span>')
    why = "".join(
        f'<span class="chip" title="P(match) = {v:.2f}"><span class="meter"><i style="width:{round(v * 100)}%"></i></span>'
        f"{_e(labels.get(k, k))} {_pct(v)}</span>"
        for k, v in d.top_interests()
    )
    meta = " · ".join(x for x in [_authors(p.authors), ", ".join(p.categories[:3])] if x)
    summary = f'<p class="tldr">{_e(d.summary)}</p>' if d.summary else ""
    abstract = f"<details><summary>Abstract</summary><p>{_e(p.abstract)}</p></details>" if p.abstract else ""
    return (
        f'<article class="card {d.band}"><div class="row">{"".join(tags)}</div>'
        f'<h3><a href="{_url(p.url)}">{_e(p.title)}</a></h3>'
        f'<p class="by">{_e(meta)}</p>{summary}<div class="why">{why}</div>{abstract}'
        f'<div class="foot"><span class="id">{_e(p.id)}</span>{_votes(d, feedback_repo)}</div></article>'
    )


def _page(config: Config, title: str, body: str) -> str:
    feed = "feed.xml"
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(title)}</title>"
        f'<link rel="alternate" type="application/rss+xml" title="{_e(config.title)}" href="{feed}">'
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
        f'<header class="top"><a class="brand" href="index.html">{LOGO}<span>{_e(config.title)}</span></a>'
        f'<nav><a href="index.html">Latest</a><a href="archive.html">Archive</a><a href="{feed}">RSS</a></nav></header>'
        f"{body}"
        f'<footer>Built with <a href="{REPO_URL}">Paper Radar</a> v{__version__}. Percentages are the model\'s '
        "probability that a paper matches your interest statement, not a quality score. "
        "Every decision is logged in <code>data/decisions/</code>. Label a paper with "
        "<code>paper-radar label &lt;id&gt; yes|no</code>, then run <code>paper-radar calibrate</code>.</footer>"
        "</div></body></html>"
    )


def render_day(
    config: Config,
    day: str,
    decisions: list[Decision],
    stats: dict[str, Any],
    *,
    mock: bool = False,
) -> str:
    labels = {i.id: i.display for i in config.interests}
    ex_labels = {e.id: e.display for e in config.exclusions}
    votes_repo = config.output.feedback_repo
    ranked = rank(decisions)
    must = [d for d in ranked if d.band == "must_read"]
    maybe = [d for d in ranked if d.band == "maybe"]
    near = [d for d in ranked if d.band == "skip"][: config.output.near_misses]
    excluded = [d for d in ranked if d.band == "excluded"]

    engine = stats.get("model") or "?"
    if stats.get("backend"):
        engine += f" via {stats['backend']}"
    meta_bits = []
    if stats.get("seconds"):
        meta_bits.append(f"{stats['seconds']:.0f} s")
    meta_bits.append(f"{_num(stats['tokens'])} input tokens")
    if not mock:
        meta_bits.append(f"≈ ${stats['cost']:.4f}")
    meta_bits.append(engine)

    banner = ""
    if mock:
        banner = (
            '<div class="banner"><b>Offline demo.</b> These papers are fictional samples and the scores come from '
            "a keyword heuristic, not Jev. Add a TypeSafe or OpenRouter key to run the real model.</div>"
        )
    # A source that was down looks exactly like a strict filter: "1 read → 1 must-read"
    # with no explanation. Say which feed was missing, so the number can be read properly.
    for failure in stats.get("source_failures") or []:
        banner += (
            f'<div class="banner warn"><b>{_e(failure["source"])} did not answer on this run.</b> '
            "The counts below cover the sources that did. "
            f'<span class="why">{_e(failure["error"])}</span></div>'
        )

    body = [
        '<section class="hero">',
        f"<h1>{_e(day)}</h1>",
        f'<p class="sub">{_e(config.output.tagline or "Every new paper was read against your interests. These are the ones worth your time.")}</p>',
        banner,
        '<div class="funnel">',
        f'<div class="stage"><b>{_num(stats["judged"])}</b><span>papers read</span></div><div class="arrow">→</div>',
        f'<div class="stage"><b>{_num(len(must) + len(maybe))}</b><span>shortlisted</span></div><div class="arrow">→</div>',
        f'<div class="stage must"><b>{_num(len(must))}</b><span>must-read</span></div>',
        "</div>",
        f'<p class="meta">{_e(" · ".join(meta_bits))}</p>',
        "</section>",
        f'<h2>Must-read <small>≥ {_pct(config.thresholds.must_read)}</small></h2>',
        "".join(_card(d, labels, votes_repo) for d in must) or '<p class="empty">Nothing crossed the must-read bar today.</p>',
        f'<h2>Maybe <small>{_pct(config.thresholds.maybe)} to {_pct(config.thresholds.must_read)}</small></h2>',
        "".join(_card(d, labels, votes_repo) for d in maybe) or '<p class="empty">No maybes today.</p>',
    ]
    if near:
        items = "".join(
            f'<li><span class="pct">{_pct(d.relevance)}</span><a href="{_url(d.paper.url)}">{_e(d.paper.title)}</a>'
            f"{_votes(d, votes_repo)}</li>"
            for d in near
        )
        body.append(
            f"<details><summary>Near misses ({len(near)}): just under your maybe bar, useful for tuning thresholds"
            f'</summary><div class="list"><ul>{items}</ul></div></details>'
        )
    if excluded:
        items = "".join(
            f'<li><a href="{_url(d.paper.url)}">{_e(d.paper.title)}</a> '
            f'<span class="tag">{_e(", ".join(ex_labels.get(k, k) for k in d.excluded_by))}</span></li>'
            for d in excluded
        )
        body.append(
            f"<details><summary>Filtered by your exclusions ({len(excluded)})</summary>"
            f'<div class="list"><ul>{items}</ul></div></details>'
        )
    return _page(config, f"{config.title} · {day}", "".join(body))


def render_archive(config: Config, rows: list[tuple[str, dict[str, Any]]]) -> str:
    lines = "".join(
        f'<tr><td><a href="{_e(day)}.html">{_e(day)}</a></td><td>{_num(s["judged"])}</td>'
        f'<td>{_num(s["maybe"] + s["must_read"])}</td><td>{_num(s["must_read"])}</td><td>${s["cost"]:.4f}</td></tr>'
        for day, s in sorted(rows, reverse=True)
    )
    body = (
        '<section class="hero"><h1>Archive</h1><p class="sub">Every run, newest first.</p></section>'
        "<table><thead><tr><th>Day</th><th>Read</th><th>Shortlisted</th><th>Must-read</th><th>Cost</th></tr></thead>"
        f"<tbody>{lines}</tbody></table>"
    )
    return _page(config, f"{config.title} · Archive", body)


def render_feed(config: Config, items: list[tuple[str, Decision]]) -> str:
    """RSS 2.0 of must-read + maybe. Subscribe in any reader, or in Zotero (File > New Feed)."""
    labels = {i.id: i.display for i in config.interests}
    site = config.output.site_url.rstrip("/")
    now = format_datetime(datetime.now(timezone.utc))
    entries = []
    for day, d in items:
        p = d.paper
        star = "★ " if d.band == "must_read" else ""
        why = ", ".join(f"{labels.get(k, k)} {_pct(v)}" for k, v in d.top_interests())
        desc = f"<p><b>{_pct(d.relevance)}</b> · {why}</p>"
        if d.summary:
            desc += f"<p>{html.escape(d.summary)}</p>"
        desc += f"<p>{html.escape(p.abstract)}</p>"
        try:
            pub = format_datetime(datetime.fromisoformat(day).replace(tzinfo=timezone.utc))
        except ValueError:
            pub = now
        entries.append(
            "<item>"
            f"<title>{xml_escape(star + p.title)}</title><link>{xml_escape(p.url)}</link>"
            f'<guid isPermaLink="false">{xml_escape(p.id)}</guid><pubDate>{pub}</pubDate>'
            + "".join(f"<category>{xml_escape(c)}</category>" for c in p.categories[:5])
            + (f"<author>{xml_escape(', '.join(p.authors[:6]))}</author>" if p.authors else "")
            + f"<description>{xml_escape(desc)}</description></item>"
        )
    self_link = f'<atom:link href="{xml_escape(site)}/feed.xml" rel="self" type="application/rss+xml"/>' if site else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{xml_escape(config.title)}</title><link>{xml_escape(site or REPO_URL)}</link>"
        "<description>Papers selected by Paper Radar</description>"
        f"<lastBuildDate>{now}</lastBuildDate>{self_link}{''.join(entries)}</channel></rss>"
    )


DIRECTORY_CSS = """
.feeds{display:grid;gap:14px;margin:22px 0 8px}
.feed-card{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:16px 18px}
.feed-card h2{margin:0 0 2px;font-size:17px;letter-spacing:-.01em}
.feed-card h2 a{color:inherit}
.feed-card .sub{margin:0 0 10px;color:var(--muted);font-size:14px}
.counts{display:flex;flex-wrap:wrap;gap:6px;align-items:baseline;font-size:14px;color:var(--muted);margin:0 0 10px}
.counts b{color:var(--text);font-variant-numeric:tabular-nums}
.counts .hit{color:var(--must)}
.peek{margin:0 0 12px;padding:0;list-style:none;font-size:14px}
.peek li{margin:2px 0;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.links{display:flex;gap:8px;flex-wrap:wrap}
.links a{display:inline-block;border:1px solid var(--border);border-radius:999px;padding:4px 12px;font-size:14px}
.quiet{color:var(--muted);font-size:14px}
.cta{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:16px 18px;margin:18px 0}
.cta h2{margin:0 0 6px;font-size:16px}
.cta p{margin:0;color:var(--muted);font-size:14px}
"""


def render_directory(radars: list[dict[str, Any]], *, title: str = "Paper Radar · live feeds") -> str:
    """A directory of every public radar, so a visitor can subscribe without forking anything.

    Each card carries the feed's own numbers from today, because "247 read, 14 kept" says
    more about what the thing does than any description of it.
    """
    # _url() sanitises links that came out of a paper feed and rewrites anything that is
    # not http(s) to "#". These are relative paths this function built, so they use _e().
    cards = []
    for r in radars:
        peek = "".join(f"<li>· {_e(t)}</li>" for t in r.get("top", [])[:3])
        counts = (
            f'<p class="counts"><b>{_num(r["judged"])}</b> read <span>→</span> '
            f'<b>{_num(r["shortlisted"])}</b> shortlisted <span>→</span> '
            f'<b class="hit">{_num(r["must_read"])}</b> worth opening '
            f'<span>· {_e(r["day"])} · ${r["cost"]:.4f}</span></p>'
            if r.get("judged") is not None
            else '<p class="counts quiet">No run recorded yet.</p>'
        )
        note = (
            f'<p class="counts quiet">⚠ {_e(", ".join(r["source_failures"]))} did not answer on this run.</p>'
            if r.get("source_failures")
            else ""
        )
        cards.append(
            f'<article class="feed-card"><h2><a href="{_e(r["url"])}">{_e(r["title"])}</a></h2>'
            f'<p class="sub">{_e(r["tagline"])}</p>{counts}{note}'
            + (f'<ul class="peek">{peek}</ul>' if peek else "")
            + f'<p class="links"><a href="{_e(r["url"])}">Open</a>'
            f'<a href="{_e(r["feed"])}">RSS</a></p></article>'
        )

    body = (
        '<section class="hero"><h1>Live feeds</h1>'
        '<p class="sub">Each one reads every new paper in its field each weekday and keeps the few that match. '
        "Take the RSS link — nothing to install, no key, no account.</p></section>"
        f'<div class="feeds">{"".join(cards)}</div>'
        '<section class="cta"><h2>Want one for your own interests?</h2>'
        f'<p>These are ordinary config files in the repo. Fork it, write what you care about in plain English, '
        f'and a GitHub Action publishes your own page and feed. <a href="{REPO_URL}">Paper Radar on GitHub</a>.</p>'
        "</section>"
    )
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(title)}</title>"
        '<meta name="description" content="Daily research feeds: every new paper in a field, '
        'judged against plain-English interests, with only the few that match kept.">'
        f"<style>{CSS}{DIRECTORY_CSS}</style></head><body><div class=\"wrap\">"
        f'<header class="top"><a class="brand" href="index.html">{LOGO}<span>{_e(title)}</span></a>'
        f'<nav><a href="{REPO_URL}">GitHub</a></nav></header>{body}'
        f'<footer>Built with <a href="{REPO_URL}">Paper Radar</a> v{__version__}. Percentages are the model\'s '
        "probability that a paper matches an interest statement, not a quality score. Every decision is logged "
        "in <code>data/</code>.</footer></div></body></html>"
    )
