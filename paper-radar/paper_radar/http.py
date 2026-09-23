"""Tiny stdlib HTTP helpers (Paper Radar has zero runtime dependencies)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from . import REPO_URL, __version__

USER_AGENT = f"paper-radar/{__version__} (+{REPO_URL})"
_RETRYABLE = {408, 429, 500, 502, 503, 504}


def http_get(url: str, *, timeout: float = 60.0, retries: int = 3, headers: dict[str, str] | None = None) -> str:
    """GET a URL and return decoded text, retrying transient failures."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as error:
            if error.code not in _RETRYABLE:
                raise
            last_error = error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = error
        if attempt < retries:
            time.sleep(min(2**attempt, 20))
    assert last_error is not None
    raise last_error


def post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None, timeout: float = 30.0) -> Any:
    """POST JSON and return the decoded JSON body (raises urllib errors on failure)."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else None
