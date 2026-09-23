"""Clients for Jev's System One endpoint.

Backends
--------
* ``typesafe``   POST {base}/v1/systemone          (TYPESAFE_API_KEY)
* ``openrouter`` POST openrouter.ai/api/alpha/decisions (OPENROUTER_API_KEY, no waitlist)
* ``mock``       offline keyword heuristic for demos and tests. It is NOT Jev.

Both HTTP backends share the same wire format: ``{"model", "state", "questions"}`` in,
``{"model", "answers", "usage"}`` out. Stdlib only, so the GitHub Action installs in seconds.
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Protocol

from .config import JevSettings
from .http import USER_AGENT
from .models import JevResult

TYPESAFE_DEFAULT_BASE = "https://api.typesafe.ai"
OPENROUTER_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODELS = {"typesafe": "jev-latest", "openrouter": "typesafe/jev-1.13", "mock": "mock-heuristic"}
KEY_ENV = {"typesafe": "TYPESAFE_API_KEY", "openrouter": "OPENROUTER_API_KEY"}

FATAL_STATUSES = {400, 401, 402, 403, 404, 422}
RETRYABLE_STATUSES = {408, 409, 429, 500, 502, 503, 504, 529}


class JevError(RuntimeError):
    def __init__(self, message: str, *, fatal: bool = False, status: int | None = None):
        super().__init__(message)
        self.fatal = fatal
        self.status = status


class Backend(Protocol):
    name: str
    model: str

    def decide(self, state: Any, questions: dict[str, dict[str, Any]]) -> JevResult: ...


class RateLimiter:
    """Spaces requests evenly to stay under the per-minute limit (TypeSafe: 1,200 req/min)."""

    def __init__(self, per_minute: int):
        self.interval = 60.0 / per_minute
        self._lock = threading.Lock()
        self._next = time.monotonic()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            self._next = max(now, self._next) + self.interval
        if wait > 0:
            time.sleep(wait)


def _retry_after(headers: Any) -> float | None:
    if headers is None:
        return None
    ms = headers.get("retry-after-ms")
    if ms:
        try:
            return min(float(ms) / 1000.0, 60.0)
        except ValueError:
            pass
    seconds = headers.get("retry-after")
    if seconds:
        try:
            return min(float(seconds), 60.0)
        except ValueError:
            return None
    return None


def _backoff(attempt: int) -> float:
    return min(0.5 * 2**attempt, 8.0) * (1 - random.random() * 0.25)


def parse_response(data: Any, questions: dict[str, dict[str, Any]], fallback_model: str) -> JevResult:
    if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
        raise JevError("Malformed response: missing 'answers'")
    answers = data["answers"]
    for key, question in questions.items():
        answer = answers.get(key)
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise JevError(f"Malformed response: answer {key!r} missing or wrong type")
        kind = question["type"]
        if kind == "noul" and not isinstance(answer.get("noul"), (int, float)):
            raise JevError(f"Malformed noul answer for {key!r}")
        if kind == "choice" and answer.get("choice") not in question["criteria"]:
            raise JevError(f"Choice answer for {key!r} is outside the criteria")
        if kind == "score" and not isinstance(answer.get("score"), (int, float)):
            raise JevError(f"Malformed score answer for {key!r}")
    usage = data.get("usage") or {}
    cost = usage.get("cost")
    return JevResult(
        answers=answers,
        model=str(data.get("model") or fallback_model),
        input_tokens=int(usage.get("input_tokens") or 0),
        cost=float(cost) if isinstance(cost, (int, float)) else None,
    )


class HTTPBackend:
    def __init__(
        self,
        *,
        name: str,
        url: str,
        api_key: str,
        model: str,
        timeout: float,
        max_retries: int,
        limiter: RateLimiter,
        extra_headers: dict[str, str] | None = None,
    ):
        self.name = name
        self.url = url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = limiter
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **(extra_headers or {}),
        }

    def decide(self, state: Any, questions: dict[str, dict[str, Any]]) -> JevResult:
        body = json.dumps({"model": self.model, "state": state, "questions": questions}).encode("utf-8")
        attempt = 0
        while True:
            self.limiter.acquire()
            request = urllib.request.Request(self.url, data=body, method="POST", headers=self._headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
                return parse_response(data, questions, self.model)
            except urllib.error.HTTPError as error:
                detail = error.read()[:300].decode("utf-8", errors="replace")
                message = f"{self.name} HTTP {error.code}: {detail}"
                if error.code in FATAL_STATUSES:
                    raise JevError(message, fatal=True, status=error.code) from None
                if error.code not in RETRYABLE_STATUSES or attempt >= self.max_retries:
                    raise JevError(message, status=error.code) from None
                delay = _retry_after(error.headers) or _backoff(attempt)
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as error:
                if attempt >= self.max_retries:
                    raise JevError(f"{self.name} request failed: {error}") from None
                delay = _backoff(attempt)
            attempt += 1
            time.sleep(delay)


# --------------------------------------------------------------------------- mock

_STOP = set(
    """a an the of to in on for with and or by from as at is are be been being this that these those it its into
    over under about via than then our we their paper papers study studies approach approaches method methods propose
    proposes proposed present presents presented show shows new novel based using use used results result work works
    analyze analyzes analysis whether which such can may also more most other main primary primarily does do what how
    abstract states state will publicly example""".split()
)


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9\-]+", text.lower()) if w not in _STOP and len(w) > 1}


def _overlap(question_text: str, state_prefixes: set[str]) -> float:
    prefixes = {t[:5] for t in _terms(question_text)}
    if not prefixes:
        return 0.0
    hits = sum(1 for t in prefixes if t in state_prefixes)
    return hits / len(prefixes)


class MockBackend:
    """Deterministic keyword-overlap stand-in so anyone can try the pipeline offline.

    Probabilities from this backend are NOT calibrated and are NOT Jev's.
    """

    name = "mock"

    def __init__(self, model: str = "mock-heuristic"):
        self.model = model

    def decide(self, state: Any, questions: dict[str, dict[str, Any]]) -> JevResult:
        text = " ".join(str(v) for v in (state.values() if isinstance(state, dict) else [state]))
        prefixes = {t[:5] for t in _terms(text)}
        answers: dict[str, dict[str, Any]] = {}
        for key, question in questions.items():
            kind = question["type"]
            if kind == "noul":
                frac = _overlap(str(question.get("instructions", "")), prefixes)
                p = 0.02 + 0.93 / (1 + math.exp(-9 * (frac - 0.4)))
                answers[key] = {"type": "noul", "noul": round(p, 4)}
            elif kind == "choice":
                labels = list(question["criteria"])
                title = str(state.get("title", "")).lower() if isinstance(state, dict) else ""
                raw = [
                    math.exp(4 * _overlap(str(question["criteria"][label]), prefixes) + (3 if label.split("_")[0][:5] in title else 0))
                    for label in labels
                ]
                total = sum(raw)
                probs = {label: round(r / total, 4) for label, r in zip(labels, raw)}
                best = max(probs, key=probs.get)
                answers[key] = {"type": "choice", "choice": best, "probabilities": probs, "confidence": probs[best]}
            else:
                levels = question["criteria"]
                probs = {str(i): (0.6 if i == 1 else 0.4 / max(1, len(levels) - 1)) for i in range(len(levels))}
                score = sum(i * p for i, p in enumerate(probs.values()))
                answers[key] = {
                    "type": "score",
                    "score": round(score, 3),
                    "legend": {str(i): level for i, level in enumerate(levels)},
                    "probabilities": probs,
                    "confidence": 0.6,
                }
        tokens = 250 + len(json.dumps(state)) // 4 + len(json.dumps(questions)) // 4
        return JevResult(answers=answers, model=self.model, input_tokens=tokens, cost=None)


# --------------------------------------------------------------------------- factory


def make_backend(settings: JevSettings, env: dict[str, str] | None = None) -> Backend:
    env = dict(os.environ if env is None else env)
    backend = settings.backend
    model = settings.model
    if not model and backend == "typesafe":
        model = env.get("TYPESAFE_DEFAULT_MODEL")
    model = model or DEFAULT_MODELS[backend]
    if backend == "mock":
        return MockBackend()

    key_name = KEY_ENV[backend]
    api_key = env.get(key_name, "").strip()
    if not api_key:
        hint = (
            "Set it as a repository secret (Settings -> Secrets and variables -> Actions) or export it locally. "
            "No TypeSafe access yet? Use backend = \"openrouter\" (no waitlist) or run `paper-radar demo`."
        )
        raise JevError(f"{key_name} is not set. {hint}", fatal=True)

    limiter = RateLimiter(settings.requests_per_minute)
    if backend == "typesafe":
        base = (settings.base_url or env.get("TYPESAFE_BASE_URL") or TYPESAFE_DEFAULT_BASE).rstrip("/")
        url = base + "/v1/systemone"
        extra: dict[str, str] = {}
    else:
        url = settings.base_url or OPENROUTER_URL
        extra = {"X-Title": "Paper Radar"}
    return HTTPBackend(
        name=backend,
        url=url,
        api_key=api_key,
        model=model,
        timeout=settings.timeout,
        max_retries=settings.max_retries,
        limiter=limiter,
        extra_headers=extra,
    )
