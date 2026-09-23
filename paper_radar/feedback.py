"""Collect 👍/👎 feedback that readers leave as GitHub issues.

Every paper on the page carries two links that open a pre-filled issue titled
`radar-label: <paper id> yes|no`. This module folds those issues into
`data/labels.jsonl` (what `paper-radar calibrate` reads) and closes them, so one
click in the browser becomes a labelled example without any other infrastructure.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import quote

from .http import USER_AGENT, http_get
from .ids import normalize_paper_id
from .store import Store

TITLE_RE = re.compile(r"^radar-label:\s*(\S+)\s+(yes|no)\b", re.IGNORECASE)
API = "https://api.github.com"
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


@dataclass
class HarvestResult:
    recorded: int = 0
    closed: int = 0
    ignored: int = 0
    errors: list[str] = field(default_factory=list)


def issue_url(repo: str, paper_id: str, title: str, link: str, verdict: str) -> str:
    """The pre-filled 'new issue' URL behind a 👍 / 👎 on the page."""
    issue_title = f"radar-label: {paper_id} {verdict}"
    body = (
        f"{title}\n{link}\n\n"
        f"Submitting this issue records **{verdict}** for `{paper_id}`.\n"
        "The next run folds it into `data/labels.jsonl`, closes this issue, and "
        "`paper-radar calibrate` uses it to fit your thresholds."
    )
    return f"https://github.com/{repo}/issues/new?title={quote(issue_title)}&body={quote(body)}"


def _default_fetch(url: str, headers: dict[str, str]) -> Any:
    return json.loads(http_get(url, headers=headers, timeout=30))


def _default_patch(url: str, payload: dict[str, Any], headers: dict[str, str]) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="PATCH",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def harvest(
    repo: str,
    store: Store,
    *,
    token: str = "",
    close: bool = True,
    fetch: Callable[[str, dict[str, str]], Any] = _default_fetch,
    patch: Callable[[str, dict[str, Any], dict[str, str]], None] = _default_patch,
    log: Callable[[str], None] = print,
) -> HarvestResult:
    if not REPO_RE.match(repo):
        raise ValueError(f"feedback repo must look like 'owner/name', got {repo!r}")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    result = HarvestResult()
    issues = fetch(f"{API}/repos/{repo}/issues?state=open&per_page=100", headers)
    if not isinstance(issues, list):
        raise ValueError("unexpected response from the GitHub issues API")

    for issue in issues:
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        match = TITLE_RE.match(str(issue.get("title", "")).strip())
        if not match:
            result.ignored += 1
            continue
        paper_id = normalize_paper_id(match.group(1))
        relevant = match.group(2).lower() == "yes"
        store.add_label(paper_id, relevant, str(issue.get("created_at", "")))
        result.recorded += 1
        number = issue.get("number")
        if close and token and number is not None:
            try:
                patch(
                    f"{API}/repos/{repo}/issues/{number}",
                    {"state": "closed", "state_reason": "completed"},
                    headers,
                )
                result.closed += 1
            except Exception as error:  # a failed close must not lose the label
                result.errors.append(f"issue #{number}: {error}")
                log(f"  ! could not close issue #{number}: {error}")
    return result
