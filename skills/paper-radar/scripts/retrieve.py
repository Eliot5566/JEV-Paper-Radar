"""Retrieve public paper metadata; no model calls, credentials or extra packages.

Only official arXiv, PubMed and Crossref endpoints are contacted. A publisher
link without a recognized identifier is reported, never scraped or guessed.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import quote, unquote, urlencode, urlsplit
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ARXIV = "https://export.arxiv.org/api/query"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
CROSSREF = "https://api.crossref.org/works/"
ARXIV_ID = r"(?:\d{4}\.\d{4,5}|[a-z][a-z.-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?"
DOI = r"10\.\d{4,9}/\S+"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
MAX_BYTES = 2_000_000


def compact(value):
    return " ".join(value.split())


def identify(value):
    """Parse identifiers without requesting user-supplied URLs."""
    value = value.strip()
    if re.fullmatch(ARXIV_ID, value.removeprefix("arxiv:").removeprefix("arXiv:")):
        return "arxiv", value.split(":", 1)[-1]
    if value.lower().startswith("doi:"):
        value = value[4:]
    if re.fullmatch(DOI, value, re.I):
        return "crossref", value.lower()
    if re.fullmatch(r"(?:pmid:|pubmed:)\d{1,10}", value, re.I):
        return "pubmed", value.split(":")[1]
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in ("http", "https") or parsed.username or parsed.password:
        raise ValueError("use an arXiv, PubMed or DOI link/identifier")
    if parsed.port not in (None, 80, 443):
        raise ValueError("unsupported URL port")
    host, path = (parsed.hostname or "").lower(), unquote(parsed.path)
    if host in ("arxiv.org", "www.arxiv.org", "export.arxiv.org"):
        match = re.fullmatch(r"/(?:abs|pdf|html)/(" + ARXIV_ID + r")(?:\.pdf)?/?", path)
        if match:
            return "arxiv", match[1]
    if host == "pubmed.ncbi.nlm.nih.gov" and re.fullmatch(r"/\d{1,10}/?", path):
        return "pubmed", path.strip("/")
    if host in ("doi.org", "dx.doi.org") and re.fullmatch(DOI, path.lstrip("/"), re.I):
        return "crossref", path.lstrip("/").lower()
    raise ValueError("unsupported link: use arXiv, PubMed or doi.org; no arbitrary page/PDF scraping")


def allowed_endpoint(url):
    p = urlsplit(url)
    return (p.scheme == "https" and not p.username and not p.password and p.port in (None, 443)
            and ((p.hostname == "export.arxiv.org" and p.path == "/api/query")
                 or (p.hostname == "eutils.ncbi.nlm.nih.gov" and p.path in (
                     "/entrez/eutils/esearch.fcgi", "/entrez/eutils/efetch.fcgi"))
                 or (p.hostname == "api.crossref.org" and p.path.startswith("/works/"))))


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_endpoint(newurl):
            raise ValueError("metadata redirect left the supported HTTPS API endpoints")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self):
        self.requests = []
        self.last = {}
        self.opener = urllib.request.build_opener(RestrictedRedirect())

    def get(self, url):
        if not allowed_endpoint(url):
            raise ValueError("unsupported metadata endpoint")
        host = urlsplit(url).hostname
        delay = 3.1 if host == "export.arxiv.org" else 0.4 if host == "eutils.ncbi.nlm.nih.gov" else 1.0
        time.sleep(max(0, delay - (time.monotonic() - self.last.get(host, -100))))
        entry = {"url": url, "status": "failed"}
        self.requests.append(entry)
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "paper-radar-skill/0.2.0 (+https://github.com/Eliot5566/JEV-Paper-Radar)",
                "Accept": "application/atom+xml, application/xml, application/json"})
            with self.opener.open(request, timeout=30) as response:
                if not allowed_endpoint(response.geturl()):
                    raise ValueError("unexpected metadata response endpoint")
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("metadata response exceeds 2 MB")
                result = data.decode("utf-8-sig")
            entry["status"] = "ok"
            return result
        except urllib.error.HTTPError as error:
            entry["http_status"] = error.code
            raise ValueError(f"metadata HTTP {error.code}; source may be unavailable, rate-limited or blocked") from error
        except (OSError, UnicodeError) as error:
            raise ValueError("metadata request failed; check source availability and permitted network access") from error
        finally:
            self.last[host] = time.monotonic()


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(value)
    return compact(" ".join(parser.parts))


def parse_arxiv(raw):
    rows = []
    for entry in ET.fromstring(raw).findall("a:entry", ATOM):
        link = entry.findtext("a:id", default="", namespaces=ATOM)
        if "/api/errors" in link:
            raise ValueError("arXiv rejected the search query")
        source, ident = identify(link)
        if source != "arxiv":
            raise ValueError("unexpected arXiv identifier")
        rows.append({"id": "arxiv:" + ident, "title": compact(entry.findtext("a:title", "", ATOM)),
                     "abstract": compact(entry.findtext("a:summary", "", ATOM)),
                     "url": "https://arxiv.org/abs/" + ident, "source": "arxiv",
                     "published": entry.findtext("a:published", "", ATOM)})
    return rows


def parse_pubmed(raw):
    root = ET.fromstring(raw)
    if root.tag == "ERROR" or root.find(".//ERROR") is not None:
        raise ValueError("PubMed returned an error")
    rows = []
    for record in root.findall(".//PubmedArticle"):
        pmid = record.findtext("./MedlineCitation/PMID", "")
        if not re.fullmatch(r"\d{1,10}", pmid):
            continue
        article = record.find("./MedlineCitation/Article")
        if article is None:
            continue
        title = article.find("ArticleTitle")
        parts = []
        for node in article.findall("./Abstract/AbstractText"):
            content = compact("".join(node.itertext()))
            if content:
                parts.append((node.get("Label", "") + ": " if node.get("Label") else "") + content)
        rows.append({"id": "pubmed:" + pmid, "title": compact("".join(title.itertext())) if title is not None else "",
                     "abstract": "\n".join(parts), "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                     "source": "pubmed", "published": "-".join(article.findtext(
                         "./Journal/JournalIssue/PubDate/" + field, "") for field in ("Year", "Month", "Day")).strip("-")})
    return rows


def parse_crossref(raw, doi):
    item = json.loads(raw)["message"]
    if str(item.get("DOI", "")).lower() != doi.lower():
        raise ValueError("Crossref returned a different DOI")
    dates = item.get("published", {}).get("date-parts", [[]])[0]
    return [{"id": "doi:" + doi, "title": plain(" ".join(item.get("title", []))),
             "abstract": plain(item.get("abstract", "")), "url": "https://doi.org/" + doi,
             "source": "crossref", "published": "-".join(map(str, dates))}]


def canonical(ident):
    return re.sub(r"v\d+$", "", ident) if ident.startswith("arxiv:") else ident


def retrieve(*, links=(), query=None, source="arxiv", limit=10, days=30, client=None, now=None):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be 1 to 20")
    if isinstance(days, bool) or not isinstance(days, int) or not 0 <= days <= 3650:
        raise ValueError("days must be 0 (no date restriction) to 3650")
    if source not in ("arxiv", "pubmed"):
        raise ValueError("search source must be arxiv or pubmed")
    if bool(links) == bool(query):
        raise ValueError("provide either links or one search query")
    if len(links) > 20 or (query and (not isinstance(query, str) or not query.strip() or len(query) > 1000)):
        raise ValueError("use at most 20 links or a non-empty query of at most 1000 characters")
    now = now or datetime.now(timezone.utc)
    client = client or Client()
    fetched = now.isoformat()
    rows, errors, groups = [], [], {"arxiv": [], "pubmed": [], "crossref": []}
    for link in links:
        try:
            provider, ident = identify(link)
            if ident not in groups[provider]:
                groups[provider].append(ident)
        except ValueError as error:
            errors.append({"input": link, "error": str(error)})
    jobs = []
    if links:
        if groups["arxiv"]:
            jobs.append(("arxiv", ARXIV + "?" + urlencode({"id_list": ",".join(groups["arxiv"]), "max_results": 20}), None))
        if groups["pubmed"]:
            jobs.append(("pubmed", NCBI + "efetch.fcgi?" + urlencode({"db": "pubmed", "tool": "paper-radar", "id": ",".join(groups["pubmed"]), "retmode": "xml"}), None))
        jobs.extend(("crossref", CROSSREF + quote(doi, safe=""), doi) for doi in groups["crossref"])
    else:
        if source == "arxiv":
            term = query.strip()
            if days:
                start = (now - timedelta(days=days)).strftime("%Y%m%d")
                term = f"({term}) AND submittedDate:[{start}0000 TO {now:%Y%m%d}2359]"
            jobs.append((source, ARXIV + "?" + urlencode({"search_query": term, "start": 0, "max_results": limit,
                         "sortBy": "relevance", "sortOrder": "descending"}), None))
        else:
            params = {"db": "pubmed", "tool": "paper-radar", "term": query.strip(), "retmax": limit,
                      "retmode": "json", "sort": "relevance"}
            if days:
                params.update(datetype="edat", reldate=days)
            url = NCBI + "esearch.fcgi?" + urlencode(params)
            try:
                result = json.loads(client.get(url))["esearchresult"]
                if result.get("ERROR") or result.get("errorlist"):
                    raise ValueError("PubMed rejected the search query")
                ids = result.get("idlist", [])[:limit]
                if any(not re.fullmatch(r"\d{1,10}", ident) for ident in ids):
                    raise ValueError("invalid PubMed search identifier")
                if ids:
                    jobs.append((source, NCBI + "efetch.fcgi?" + urlencode({"db": "pubmed", "tool": "paper-radar", "id": ",".join(ids), "retmode": "xml"}), None))
            except (ValueError, KeyError, TypeError, OSError) as error:
                errors.append({"source": source, "error": str(error)})
    for provider, url, doi in jobs:
        try:
            raw = client.get(url)
            batch = parse_arxiv(raw) if provider == "arxiv" else parse_pubmed(raw) if provider == "pubmed" else parse_crossref(raw, doi)
            for row in batch[:20]:
                if links and row["id"].split(":", 1)[1] not in groups[provider]:
                    # arXiv may return an explicit version for an unversioned ID.
                    wanted = {canonical(provider + ":" + x) for x in groups[provider]}
                    if canonical(row["id"]) not in wanted:
                        continue
                row.update(metadata_url=url, retrieved_at=fetched, abstract_kind="source-abstract")
                rows.append(row)
        except (ValueError, KeyError, TypeError, IndexError, ET.ParseError, OSError) as error:
            errors.append({"source": provider, "metadata_url": url, "error": str(error)})
    unique = {canonical(row["id"]): row for row in rows}
    if links:
        for provider, ids in groups.items():
            for ident in ids:
                key = ("doi:" if provider == "crossref" else provider + ":") + ident
                if canonical(key) not in unique:
                    errors.append({"input": key, "error": "no matching metadata record retrieved"})
    # Link resolution must account for every requested link, even when limit is small.
    selected = list(unique.values()) if links else list(unique.values())[:limit]
    papers, missing = [], []
    for row in selected:
        if row["title"] and row["abstract"]:
            papers.append(row)
        else:
            row["status"] = "missing_abstract" if not row["abstract"] else "missing_title"
            missing.append(row)
    status = "partial" if papers and (missing or errors) else "ok" if papers else "failed" if errors else "empty"
    return {"input_kind": "retrieved", "interest": "", "papers": papers,
            "retrieval": {"status": status, "retrieved_at": fetched, "query": query,
                          "source": source if query else "links", "days": days if query else None,
                          "limit": limit if query else len(links), "requested_links": list(links),
                          "requests": client.requests, "missing_abstracts": missing, "errors": errors,
                          "model_api_requests": 0,
                          "notice": "Public metadata only; not full text or exhaustive coverage. PubMed date filter uses indexing date. Missing abstracts require manual review. NCBI disclaimer: https://www.ncbi.nlm.nih.gov/About/disclaimer.html"}}


def write_result(result, out):
    out = Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("choose a new or empty output directory")
    out.mkdir(parents=True, exist_ok=True)
    (out / "papers.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["id", "title", "abstract", "url", "source", "published", "retrieved_at", "metadata_url", "abstract_kind"]
    with (out / "papers.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result["papers"]:
            writer.writerow({k: "'" + row[k] if row[k].lstrip().startswith(("=", "+", "-", "@")) else row[k] for k in fields})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--links", nargs="+", help="arXiv, PubMed or DOI links/IDs (max 20)")
    group.add_argument("--query", help="search query prepared from the user's interest")
    parser.add_argument("--source", choices=["arxiv", "pubmed"], default="arxiv")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--days", type=int, default=30, help="date window; 0 means no restriction")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        out = Path(args.out)
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise ValueError("choose a new or empty output directory before retrieving")
        result = retrieve(links=args.links or (), query=args.query, source=args.source, limit=args.limit, days=args.days)
        write_result(result, out)
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")
    audit = result["retrieval"]
    print(json.dumps({"status": audit["status"], "papers": len(result["papers"]), "missing_abstracts": len(audit["missing_abstracts"]),
                      "errors": len(audit["errors"]), "metadata_requests": len(audit["requests"]), "model_api_requests": 0,
                      "output": str(Path(args.out).resolve())}))
    if not result["papers"]:
        parser.exit(2, "No complete abstracts retrieved. See papers.json; do not invent or score missing abstracts.\n")


if __name__ == "__main__":
    main()
