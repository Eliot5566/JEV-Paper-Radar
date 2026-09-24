"""PubMed via NCBI E-utilities (esearch + efetch).

Two calls per batch: `esearch` turns a PubMed query into PMIDs, `efetch` returns the
records as XML. Both are public; an `NCBI_API_KEY` in the environment raises the rate
limit from 3 to 10 requests per second, which is the only thing it changes here.

Three things about PubMed records that matter and are easy to get wrong:

* **Errata and comments are records too.** "Correction to: ..." arrives as a normal
  result with PublicationType "Published Erratum". They are dropped by default, the
  same way arXiv replacements are, and `exclude_types` makes that configurable.
* **Plenty of records have no abstract at all.** They are kept, not silently dropped,
  because a systematic review has to account for every record it saw. Screening mode
  routes them to manual review instead of judging them on a title.
* **New records carry no MeSH terms.** Indexing lags by weeks (Status="In-Process"),
  so a MeSH-based filter silently misses exactly the papers a daily alert is for.
  Everything here works off the title and abstract.
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from ..models import Paper

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "paper-radar"
ABSTRACT_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

# efetch accepts far more, but a long URL of PMIDs is the part that breaks first.
BATCH = 200
# esearch returns at most 10,000 UIDs for a single query (NCBI limit).
MAX_ESEARCH = 10_000

# Record types that are not new studies. Errata and comments would otherwise show up
# every time the paper they refer to is corrected.
DEFAULT_EXCLUDE_TYPES = ("Published Erratum", "Comment", "Retraction of Publication")

_SLEEP = time.sleep


def _delay(api_key: str) -> float:
    """NCBI allows 3 requests/second without a key and 10 with one."""
    return 0.11 if api_key else 0.34


def _params(source: dict[str, Any], api_key: str) -> dict[str, str]:
    common = {"db": "pubmed", "tool": TOOL}
    email = str(source.get("email") or "").strip()
    if email:
        common["email"] = email
    if api_key:
        common["api_key"] = api_key
    return common


def fetch_pubmed(
    source: dict[str, Any], *, getter: Callable[[str], str], base_dir: Path
) -> list[Paper]:
    exclude_types = {str(t) for t in source.get("exclude_types", DEFAULT_EXCLUDE_TYPES)}

    if source.get("file"):  # offline fixture: an efetch XML response
        return parse_pubmed((base_dir / source["file"]).read_text(encoding="utf-8"), exclude_types)

    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    common = _params(source, api_key)
    limit = min(int(source.get("max_records", 500)), MAX_ESEARCH)

    search = dict(common)
    search.update(
        term=str(source["query"]),
        datetype=str(source.get("datetype", "edat")),
        reldate=str(int(source.get("days", 1))),
        retmax=str(limit),
        retmode="json",
    )
    payload = getter(f"{EUTILS}/esearch.fcgi?{urlencode(search)}")
    pmids = parse_esearch(payload)
    if not pmids:
        return []

    papers: list[Paper] = []
    pause = _delay(api_key)
    for index in range(0, len(pmids), BATCH):
        if index:
            _SLEEP(pause)
        chunk = dict(common)
        chunk.update(id=",".join(pmids[index : index + BATCH]), retmode="xml")
        papers.extend(parse_pubmed(getter(f"{EUTILS}/efetch.fcgi?{urlencode(chunk)}"), exclude_types))
    return papers


def parse_esearch(payload: str) -> list[str]:
    """Pull the PMID list out of an esearch JSON response.

    NCBI returns the counts as strings ("count": "78"), so nothing here is coerced to
    int: the list length is what the caller needs.
    """
    import json

    data = json.loads(payload)
    result = data.get("esearchresult") or {}
    if result.get("ERROR"):
        raise ValueError(f"pubmed esearch: {result['ERROR']}")
    return [str(pmid) for pmid in (result.get("idlist") or []) if str(pmid).strip()]


def _abstract(article: ET.Element) -> str:
    """Join a structured abstract back into one block, keeping its section labels.

    PubMed abstracts come either as a single <AbstractText> or as several labelled ones
    (BACKGROUND / METHODS / RESULTS / ...). The labels are worth keeping: screening
    criteria are often about the methods section specifically.
    """
    parts: list[str] = []
    for node in article.findall("./Abstract/AbstractText"):
        text = " ".join("".join(node.itertext()).split())
        if not text:
            continue
        label = (node.get("Label") or "").strip()
        parts.append(f"{label.title()}: {text}" if label else text)
    return "\n".join(parts)


def parse_pubmed(xml: str, exclude_types: set[str] | None = None) -> list[Paper]:
    exclude_types = exclude_types or set()
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise ValueError(f"pubmed efetch returned unparseable XML: {error}") from error

    papers: list[Paper] = []
    for record in root.findall(".//PubmedArticle"):
        pmid = (record.findtext("./MedlineCitation/PMID") or "").strip()
        article = record.find("./MedlineCitation/Article")
        if not pmid or article is None:
            continue

        types = [(t.text or "").strip() for t in article.findall("./PublicationTypeList/PublicationType")]
        if exclude_types & set(types):
            continue

        # `element or default` is a trap here: an Element with no children is falsy in
        # ElementTree, so a perfectly good <ArticleTitle>text</ArticleTitle> would be
        # thrown away. Test for None explicitly. itertext() is needed because titles
        # carry inline markup (<i>, <sub>) around gene and species names.
        title_node = article.find("./ArticleTitle")
        title = "" if title_node is None else " ".join("".join(title_node.itertext()).split())
        if not title:
            continue

        journal = (article.findtext("./Journal/ISOAbbreviation") or article.findtext("./Journal/Title") or "").strip()
        authors = []
        for author in article.findall("./AuthorList/Author"):
            last, initials = author.findtext("LastName"), author.findtext("Initials")
            if last:
                authors.append(f"{last} {initials}".strip())
            elif author.findtext("CollectiveName"):
                authors.append(author.findtext("CollectiveName").strip())

        published = "-".join(
            part for part in (
                record.findtext("./MedlineCitation/Article/Journal/JournalIssue/PubDate/Year") or "",
                record.findtext("./MedlineCitation/Article/Journal/JournalIssue/PubDate/Month") or "",
            ) if part
        )

        papers.append(
            Paper(
                id=f"pubmed:{pmid}",
                source="pubmed",
                title=title,
                abstract=_abstract(article),
                url=ABSTRACT_URL.format(pmid=pmid),
                authors=authors,
                categories=[journal] if journal else [],
                published=published,
                announce_type="new",
            )
        )
    return papers
