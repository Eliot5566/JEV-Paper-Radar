"""Clients for Jev's System One endpoint, plus a Claude backend.

Backends
--------
* ``typesafe``   POST {base}/v1/systemone          (TYPESAFE_API_KEY)
* ``openrouter`` POST openrouter.ai/api/alpha/decisions (OPENROUTER_API_KEY, no waitlist)
* ``claude``     POST api.anthropic.com/v1/messages (ANTHROPIC_API_KEY)
* ``gemini``     POST generativelanguage.googleapis.com/v1beta/decisions (GEMINI_API_KEY)
* ``mock``       offline keyword heuristic for demos and tests. It is NOT Jev.

Both HTTP backends share the same wire format: ``{"model", "state", "questions"}`` in,
``{"model", "answers", "usage"}`` out. Stdlib only, so the GitHub Action installs in seconds.

The Claude backend is different in one important way: Claude is a generative
model, not a System One decision model, so it has no calibrated probabilities
to return. It is asked for a JSON object of self-reported
probabilities, and those numbers are NOT calibrated. (No ``temperature`` is
sent: Haiku 5.5 rejects it with 400 "`temperature` is deprecated for this
model", verified against the live API 2026-11-11.) Treat them like the mock
backend's numbers: run ``paper-radar calibrate`` on your own labels and fit
your thresholds to them before trusting a run. The Cochrane screening numbers
in the README were measured with Jev and do NOT apply to Claude.

The Gemini backend is different in the other direction: Gemini Decision 1
is a real decision model, like Jev — it scores the same three question
types (noul / choice / score) in one forward pass and returns calibrated
probabilities, so no JSON is parsed out of prose and no repair attempt is
needed. Two things to know before trusting it the way you trust Jev: the
calibration claim is Google's (lowest calibration error on its own
benchmark suite), not a measurement on your data — run
``paper-radar calibrate`` on your own labels before trusting its
thresholds; and its noul is clamped to [0.01, 0.99], so it never claims
certainty and a threshold above 0.99 can never match. It bills input only
($0.10 per million input tokens, $0 output) and has a no-cost tier in AI
Studio for prototyping. Text input only: Paper Radar judges title and
abstract, so the Decisions API's multimodal input is not used.
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
from .usage import response_usage

TYPESAFE_DEFAULT_BASE = "https://api.typesafe.ai"
OPENROUTER_URL = "https://openrouter.ai/api/alpha/decisions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
# Latest Haiku as of 2026-11-11 (released 2026-10-07, model id claude-haiku-5-5).
# If Anthropic ships a newer Haiku, set jev.model in radar.toml instead of
# editing this default; do not assume a dateless id moves to the new model.
DEFAULT_MODELS = {
    "typesafe": "jev-latest",
    "openrouter": "typesafe/jev-1.13",
    "claude": "claude-haiku-5-5",
    "gemini": "gemini-decision-1",
    "mock": "mock-heuristic",
}
KEY_ENV = {
    "typesafe": "TYPESAFE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

FATAL_STATUSES = {400, 401, 402, 403, 404, 422}
RETRYABLE_STATUSES = {408, 409, 429, 500, 502, 503, 504, 529}


class JevError(RuntimeError):
    def __init__(self, message: str, *, fatal: bool = False, status: int | None = None):
        super().__init__(message)
        self.fatal = fatal
        self.status = status
        self.request_usage: list[dict[str, Any]] = []


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
        if kind == "noul":
            value = answer.get("noul")
            if not _is_number(value) or not 0 <= value <= 1:
                raise JevError(f"Malformed noul answer for {key!r}: expected a number in [0, 1]")
        if kind == "choice" and answer.get("choice") not in question["criteria"]:
            raise JevError(f"Choice answer for {key!r} is outside the criteria")
        if kind == "score":
            value = answer.get("score")
            if not _is_number(value) or not 0 <= value <= len(question["criteria"]) - 1:
                raise JevError(f"Malformed score answer for {key!r}: expected a number within the criteria range")
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
        records: list[dict[str, Any]] = []
        try:
            result = self._decide(state, questions, records)
        except JevError as error:
            error.request_usage = records or [response_usage({})]
            raise
        result.request_usage = records
        return result

    def _decide(self, state: Any, questions: dict[str, dict[str, Any]], records: list[dict[str, Any]]) -> JevResult:
        body = json.dumps({"model": self.model, "state": state, "questions": questions}).encode("utf-8")
        attempt = 0
        while True:
            self.limiter.acquire()
            request = urllib.request.Request(self.url, data=body, method="POST", headers=self._headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
                records.append(response_usage(data))
                return parse_response(data, questions, self.model)
            except urllib.error.HTTPError as error:
                records.append(response_usage({}))
                detail = error.read()[:300].decode("utf-8", errors="replace")
                message = f"{self.name} HTTP {error.code}: {detail}"
                if error.code in FATAL_STATUSES:
                    raise JevError(message, fatal=True, status=error.code) from None
                if error.code not in RETRYABLE_STATUSES or attempt >= self.max_retries:
                    raise JevError(message, status=error.code) from None
                delay = _retry_after(error.headers) or _backoff(attempt)
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as error:
                records.append(response_usage({}))
                if attempt >= self.max_retries:
                    raise JevError(f"{self.name} request failed: {error}") from None
                delay = _backoff(attempt)
            attempt += 1
            time.sleep(delay)


# --------------------------------------------------------------------------- claude

CLAUDE_SYSTEM = (
    "You judge research papers against plain-English statements. "
    "The paper comes in the user message as JSON; the questions are listed below. "
    "Answer with ONLY a JSON object keyed by question. "
    "For each question key, give a number between 0 and 1 for a 'noul' question "
    "(your probability that the statement is true of the paper), the exact label "
    "string for a 'choice' question (one of its criteria keys), and a number for "
    "a 'score' question (between 0 and the number of criteria minus 1)."
)


CLAUDE_REPAIR = (
    "Your previous reply could not be used: {reason} "
    "Reply with ONLY a JSON object keyed by question, no prose, no markdown fences. "
    "For each 'noul' question give a number between 0 and 1; for each 'choice' "
    "question give the exact label string; for each 'score' question give a number."
)

# Effort levels the Messages API accepts in output_config.effort. "" means
# "send no effort and use the model's default" (for models without effort).
CLAUDE_EFFORTS = ("low", "medium", "high", "xhigh", "max")
CLAUDE_DEFAULT_EFFORT = "low"
CLAUDE_MAX_TOKENS = 2048


def _claude_question_spec(questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Every question with its expected shape, as Claude reads it."""
    spec: dict[str, Any] = {}
    for key, question in questions.items():
        kind = question["type"]
        entry: dict[str, Any] = {"type": kind, "instructions": question.get("instructions", "")}
        if kind in ("choice", "score"):
            entry["criteria"] = list(question["criteria"])
        if question.get("criteria") and kind == "noul":
            entry["criteria"] = question["criteria"]
        spec[key] = entry
    return spec


def _claude_system_blocks(questions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The fixed part of every request: instructions, then the questions.

    The questions are the same for every paper in a run, so they sit in the
    system prompt ahead of the paper and end with a cache breakpoint: from the
    second paper on, this prefix is read from the prompt cache instead of
    being billed as fresh input. The JSON is sorted so the bytes, and the
    cache key, do not depend on dict order. A prefix shorter than the model's
    minimum cacheable length (512 tokens on Haiku 5.5) is simply not cached;
    that is harmless.
    """
    spec = json.dumps(_claude_question_spec(questions), ensure_ascii=False, sort_keys=True)
    return [
        {"type": "text", "text": CLAUDE_SYSTEM},
        {
            "type": "text",
            "text": "Questions (answer every key):\n" + spec,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _claude_user_text(state: Any) -> str:
    """The one user message: the paper, and nothing that is the same for every paper."""
    return "Paper:\n" + json.dumps(state, ensure_ascii=False)


def claude_output_schema(questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A JSON schema for ``output_config.format``: one key per question.

    Structured outputs guarantee the reply parses and has every key with the
    right JSON type, and a choice is constrained to its labels with ``enum``.
    The API does not support ``minimum``/``maximum``, so the 0..1 range of a
    noul and the range of a score are still checked in ``parse_claude_answers``.
    """
    properties: dict[str, Any] = {}
    for key, question in questions.items():
        kind = question["type"]
        if kind == "noul":
            properties[key] = {"type": "number", "description": "Probability from 0 to 1"}
        elif kind == "choice":
            properties[key] = {"type": "string", "enum": list(question["criteria"])}
        elif kind == "score":
            top = len(question["criteria"]) - 1
            properties[key] = {"type": "number", "description": f"A number from 0 to {top}"}
        else:
            raise JevError(f"Unknown question type {kind!r} for {key!r}")
    return {
        "type": "object",
        "properties": properties,
        "required": list(questions),
        "additionalProperties": False,
    }


def _extract_claude_text(data: Any) -> str:
    """The text of a Messages API response, or a JevError if there is none."""
    if not isinstance(data, dict) or not isinstance(data.get("content"), list):
        raise JevError("Malformed Claude response: missing 'content'")
    stop = data.get("stop_reason")
    parts = [
        block.get("text", "")
        for block in data["content"]
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "".join(parts).strip()
    if not text:
        if stop == "max_tokens":
            raise JevError("Malformed Claude response: hit max_tokens before answering")
        raise JevError("Malformed Claude response: no text content")
    return text


def _extract_json_object(text: str) -> Any:
    """Parse the first balanced {...} object in text (tolerates surrounding prose)."""
    start = text.find("{")
    if start < 0:
        raise JevError("Malformed Claude response: not valid JSON (no object found)") from None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as error:
                    raise JevError(f"Malformed Claude response: not valid JSON ({error})") from None
    raise JevError("Malformed Claude response: not valid JSON (unbalanced braces)") from None


def _parse_claude_json(text: str) -> Any:
    """Parse the model's JSON, tolerating a ```json fence or prose around it."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]  # ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Fallback: the model wrapped the object in prose — take the first
    # balanced {...}. Still raises if there is no balanced object.
    return _extract_json_object(stripped)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_number(value: Any) -> float | None:
    """A number, or a string that parses as one ("0.85"); anything else is None.

    The model sometimes writes a probability as a string. That is a
    representation slip, not a different judgement, so it is coerced; a
    non-numeric string, null, or a boolean is still rejected.
    """
    if _is_number(value):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def parse_claude_answers(
    raw: Any, questions: dict[str, dict[str, Any]], fallback_model: str, usage: dict[str, Any] | None = None
) -> JevResult:
    """Validate Claude's JSON object into the same JevResult shape Jev returns.

    Strict on purpose: a missing key, a wrong type, a probability outside
    0..1, or a choice label that is not one of the criteria is a JevError,
    not a guess. The numbers that survive are self-reported by Claude and
    are NOT calibrated — see the module docstring.
    """
    if not isinstance(raw, dict):
        raise JevError("Malformed Claude response: expected a JSON object keyed by question")
    answers: dict[str, dict[str, Any]] = {}
    for key, question in questions.items():
        if key not in raw:
            raise JevError(f"Malformed Claude response: missing answer for {key!r}")
        value = raw[key]
        kind = question["type"]
        if kind == "noul":
            if isinstance(value, dict):
                value = value.get("noul", value.get("probability"))
            number = _coerce_number(value)
            if number is None or not 0 <= number <= 1:
                raise JevError(f"Malformed Claude response: {key!r} noul must be a number in [0, 1]")
            answers[key] = {"type": "noul", "noul": round(number, 4)}
        elif kind == "choice":
            if isinstance(value, dict):
                value = value.get("choice")
            criteria = question["criteria"]
            if not isinstance(value, str) or value not in criteria:
                raise JevError(f"Malformed Claude response: {key!r} choice must be one of {sorted(criteria)}")
            answers[key] = {"type": "choice", "choice": value}
        elif kind == "score":
            if isinstance(value, dict):
                value = value.get("score")
            levels = list(question["criteria"])
            number = _coerce_number(value)
            if number is None or not 0 <= number <= len(levels) - 1:
                raise JevError(
                    f"Malformed Claude response: {key!r} score must be a number in [0, {len(levels) - 1}]"
                )
            answers[key] = {
                "type": "score",
                "score": round(number, 3),
                "legend": {str(i): level for i, level in enumerate(levels)},
            }
        else:
            raise JevError(f"Malformed Claude response: unknown question type {kind!r} for {key!r}")
    usage = usage or {}
    return JevResult(
        answers=answers,
        model=fallback_model,
        input_tokens=int(usage.get("input_tokens") or 0),
        cost=None,  # Anthropic reports tokens, not cost; the pipeline estimates from them.
    )


class ClaudeRefusal(JevError):
    """Claude declined to answer (``stop_reason: "refusal"``). Not repaired."""


class ClaudeBackend:
    """Claude as the judge, via the Anthropic Messages API (stdlib urllib only).

    One call per paper, asking for a JSON object of self-reported
    probabilities. The key is read from ANTHROPIC_API_KEY at runtime and is
    never stored anywhere by this code.

    What each request uses, and why:

    * Structured outputs (``output_config.format``): the reply is constrained
      to a JSON schema with one key per question, so it always parses and a
      choice is always one of its labels. Ranges (0..1) are still checked.
    * ``output_config.effort`` (default ``low``): this is a small
      classification task, and Haiku 5.5 otherwise defaults to ``medium``,
      spending output tokens on thinking that a yes/no judgement rarely needs.
    * Prompt caching: the instructions and questions are the same for every
      paper, so they come first, in the system prompt, with a cache
      breakpoint; the paper comes last.
    * ``decide_batch`` sends a whole run through the Message Batches API
      (half price, no rate-limit pacing) when ``jev.batch = true``.

    Differences from the Jev backends, stated plainly: Claude has no
    calibrated probabilities, so the numbers it returns must be re-calibrated
    with ``paper-radar calibrate`` before the thresholds mean anything. A
    malformed answer still gets a single repair attempt in which the model's
    own reply is echoed back as an assistant turn (an ordinary multi-turn
    exchange, ending on a user turn) with what was wrong with it. A second bad
    answer raises, and the pipeline quarantines the paper after repeated
    failures instead of retrying it every day. A refusal is not repaired.
    """

    name = "claude"

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        timeout: float,
        max_retries: int,
        limiter: RateLimiter,
        effort: str = CLAUDE_DEFAULT_EFFORT,
        batch_poll_seconds: float = 30.0,
        batch_timeout_minutes: float = 120.0,
        sleep: Any = time.sleep,
    ):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = limiter
        self.effort = effort
        self.batch_poll_seconds = batch_poll_seconds
        self.batch_timeout_minutes = batch_timeout_minutes
        self._sleep = sleep
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    # ------------------------------------------------------------ request body

    def _body(self, questions: dict[str, dict[str, Any]], messages: list[dict[str, str]]) -> dict[str, Any]:
        output_config: dict[str, Any] = {
            "format": {"type": "json_schema", "schema": claude_output_schema(questions)},
        }
        if self.effort:
            output_config["effort"] = self.effort
        # No "temperature": claude-haiku-5-5 rejects it with
        # 400 "`temperature` is deprecated for this model".
        return {
            "model": self.model,
            "max_tokens": CLAUDE_MAX_TOKENS,
            "system": _claude_system_blocks(questions),
            "messages": messages,
            "output_config": output_config,
        }

    def _answer(self, data: Any, questions: dict[str, dict[str, Any]]) -> tuple[str, JevResult]:
        """Parse one Messages API reply. Returns (text, result) or raises JevError."""
        if isinstance(data, dict) and data.get("stop_reason") == "refusal":
            raise ClaudeRefusal("Claude declined to judge this paper (stop_reason: refusal)")
        text = _extract_claude_text(data)
        raw = _parse_claude_json(text)
        return text, parse_claude_answers(raw, questions, self.model, usage=data.get("usage") or {})

    # ------------------------------------------------------------- one paper

    def decide(self, state: Any, questions: dict[str, dict[str, Any]]) -> JevResult:
        records: list[dict[str, Any]] = []
        try:
            result = self._decide(state, questions, records)
        except JevError as error:
            error.request_usage = records or [response_usage({})]
            raise
        result.request_usage = records
        result.input_tokens = sum(r.get("input_tokens") or 0 for r in records)
        return result

    def _decide(
        self,
        state: Any,
        questions: dict[str, dict[str, Any]],
        records: list[dict[str, Any]],
        first_reply: Any = None,
    ) -> JevResult:
        """Judge one paper. ``first_reply`` is an already-received (batch) reply
        whose answer was malformed: it skips straight to the repair turn."""
        user_text = _claude_user_text(state)
        messages: list[dict[str, str]] = [{"role": "user", "content": user_text}]
        repaired = False
        pending = first_reply
        attempt = 0
        while True:
            if pending is not None:
                data, pending = pending, None
            else:
                self.limiter.acquire()
                body = json.dumps(self._body(questions, messages)).encode("utf-8")
                request = urllib.request.Request(self.url, data=body, method="POST", headers=self._headers)
                try:
                    with urllib.request.urlopen(request, timeout=self.timeout) as response:
                        data = json.loads(response.read())
                except urllib.error.HTTPError as error:
                    records.append(response_usage({}))
                    detail = error.read()[:300].decode("utf-8", errors="replace")
                    message = f"{self.name} HTTP {error.code}: {detail}"
                    if error.code in FATAL_STATUSES:
                        raise JevError(message, fatal=True, status=error.code) from None
                    if error.code not in RETRYABLE_STATUSES or attempt >= self.max_retries:
                        raise JevError(message, status=error.code) from None
                    attempt += 1
                    self._sleep(_retry_after(error.headers) or _backoff(attempt - 1))
                    continue
                except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as error:
                    records.append(response_usage({}))
                    if attempt >= self.max_retries:
                        raise JevError(f"{self.name} request failed: {error}") from None
                    attempt += 1
                    self._sleep(_backoff(attempt - 1))
                    continue
                records.append(response_usage(data))
            # A malformed model answer gets ONE repair attempt: the model's
            # own reply is echoed back with what was wrong with it. (This is
            # an ordinary multi-turn exchange, not an assistant prefill — the
            # conversation still ends on a user turn.) A second bad answer
            # raises, so a systematically bad prompt still surfaces instead of
            # burning retries.
            text = ""
            try:
                if isinstance(data, dict) and data.get("stop_reason") == "refusal":
                    raise ClaudeRefusal("Claude declined to judge this paper (stop_reason: refusal)")
                text = _extract_claude_text(data)
                raw = _parse_claude_json(text)
                return parse_claude_answers(raw, questions, self.model, usage=data.get("usage") or {})
            except ClaudeRefusal:
                raise
            except JevError as error:
                if repaired:
                    raise
                repaired = True
                messages = [{"role": "user", "content": user_text}]
                if text:
                    messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": CLAUDE_REPAIR.format(reason=error)})

    # ------------------------------------------------------------- batches

    def _batches_url(self) -> str:
        base = self.url.rstrip("/")
        return base + "/batches" if base.endswith("/messages") else base + "/v1/messages/batches"

    def _http(self, method: str, url: str, payload: Any = None, *, raw: bool = False) -> Any:
        """One Batches API call with the same retry rules as a Messages call."""
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        attempt = 0
        while True:
            request = urllib.request.Request(url, data=body, method=method, headers=self._headers)
            try:
                with urllib.request.urlopen(request, timeout=max(self.timeout, 60.0)) as response:
                    content = response.read()
                return content.decode("utf-8") if raw else json.loads(content)
            except urllib.error.HTTPError as error:
                detail = error.read()[:300].decode("utf-8", errors="replace")
                message = f"{self.name} batch HTTP {error.code}: {detail}"
                if error.code in FATAL_STATUSES:
                    raise JevError(message, fatal=True, status=error.code) from None
                if error.code not in RETRYABLE_STATUSES or attempt >= self.max_retries:
                    raise JevError(message, status=error.code) from None
                delay = _retry_after(error.headers) or _backoff(attempt)
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as error:
                if attempt >= self.max_retries:
                    raise JevError(f"{self.name} batch request failed: {error}") from None
                delay = _backoff(attempt)
            attempt += 1
            self._sleep(delay)

    def decide_batch(
        self,
        states: list[Any],
        questions: dict[str, dict[str, Any]],
        log: Any = print,
    ) -> list[JevResult | JevError]:
        """Judge many papers through the Message Batches API, in input order.

        Returns one outcome per paper, except after a fatal error, where the
        list stops early.

        Batch requests are billed at half the standard rate (and the prompt
        cache still applies), and they are not paced by the per-minute rate
        limiter. Results usually arrive within minutes; if the batch has not
        ended after ``batch_timeout_minutes`` it is cancelled and the papers
        that have no result are judged one by one instead, so a slow batch
        never costs a day's run. A paper whose batch answer is malformed, or
        whose request errored or expired, also falls back to an ordinary
        call (with the usual repair attempt). Every request's usage is
        recorded; batch records carry ``"batch": true`` so cost estimates
        apply the discount.
        """
        if not states:
            return []
        url = self._batches_url()
        requests = [
            {"custom_id": f"p{i}", "params": self._body(questions, [{"role": "user", "content": _claude_user_text(s)}])}
            for i, s in enumerate(states)
        ]
        created = self._http("POST", url, {"requests": requests})
        batch_id = str(created.get("id") or "") if isinstance(created, dict) else ""
        if not batch_id:
            raise JevError("Malformed batch response: missing 'id'")
        log(f"  … submitted {len(states)} papers as Claude batch {batch_id}")
        deadline = time.monotonic() + self.batch_timeout_minutes * 60
        status = created
        while not (isinstance(status, dict) and status.get("processing_status") == "ended"):
            if time.monotonic() >= deadline:
                log(f"  ! batch {batch_id} not finished after {self.batch_timeout_minutes:g} min; cancelling and judging the rest one by one")
                try:
                    status = self._http("POST", f"{url}/{batch_id}/cancel", {})
                except JevError:
                    status = {}
                break
            self._sleep(self.batch_poll_seconds)
            status = self._http("GET", f"{url}/{batch_id}")
        replies: dict[str, Any] = {}
        results_url = status.get("results_url") if isinstance(status, dict) else None
        if results_url and status.get("processing_status") == "ended":
            text = self._http("GET", results_url, raw=True)
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and isinstance(item.get("result"), dict):
                    replies[str(item.get("custom_id"))] = item["result"]

        outcomes: list[JevResult | JevError] = []
        fallbacks = 0
        for i, state in enumerate(states):
            reply = replies.get(f"p{i}")
            records: list[dict[str, Any]] = []
            first_reply = None
            if reply and reply.get("type") == "succeeded" and isinstance(reply.get("message"), dict):
                message = reply["message"]
                record = response_usage(message)
                record["batch"] = True
                records.append(record)
                try:
                    _, result = self._answer(message, questions)
                except ClaudeRefusal as error:
                    error.request_usage = records
                    outcomes.append(error)
                    continue
                except JevError:
                    first_reply = message  # repair it with an ordinary call
                else:
                    result.request_usage = records
                    result.input_tokens = sum(r.get("input_tokens") or 0 for r in records)
                    outcomes.append(result)
                    continue
            fallbacks += 1
            try:
                result = self._decide(state, questions, records, first_reply=first_reply)
            except JevError as error:
                error.request_usage = records or [response_usage({})]
                outcomes.append(error)
                if error.fatal:
                    # A bad key or a disallowed request will fail every paper:
                    # stop here. The papers after this one get no outcome, the
                    # same as papers left unjudged when a threaded run stops.
                    break
                continue
            result.request_usage = records
            result.input_tokens = sum(r.get("input_tokens") or 0 for r in records)
            outcomes.append(result)
        if fallbacks:
            log(f"  … {fallbacks} paper(s) judged one by one after the batch (malformed, errored or expired)")
        return outcomes


# --------------------------------------------------------------------------- gemini


def _gemini_questions(questions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Translate Jev's question dicts into the Decisions API's shape.

    The three types and their meaning are the same — Google copied Jev's
    API shape, down to the name "noul". One field differs: a noul's
    true/false descriptions live under ``criteria`` as ``true`` / ``false``
    in Jev's dicts, but the Decisions API wants them as
    ``true_description`` / ``false_description`` inside ``criteria``.
    Choice criteria (label -> description) and score criteria (ordered
    list) pass through unchanged. The caller's dicts are not mutated.
    """
    translated: dict[str, dict[str, Any]] = {}
    for key, question in questions.items():
        kind = question["type"]
        entry: dict[str, Any] = {"type": kind, "instructions": question.get("instructions", "")}
        if kind == "noul":
            criteria = question.get("criteria") or {}
            descriptions = {
                "true_description": criteria.get("true"),
                "false_description": criteria.get("false"),
            }
            descriptions = {k: v for k, v in descriptions.items() if v}
            if descriptions:
                entry["criteria"] = descriptions
        elif kind == "choice":
            entry["criteria"] = dict(question["criteria"])
        elif kind == "score":
            entry["criteria"] = list(question["criteria"])
        else:
            raise JevError(f"Unknown question type {kind!r} for {key!r}")
        translated[key] = entry
    return translated


def _gemini_input_text(state: Any) -> str:
    """The one text input: the paper as JSON, the same content Claude sees.

    The Decisions API also takes images, audio, video and PDFs, but Paper
    Radar judges title and abstract text, so a plain string input is the
    whole request.
    """
    return json.dumps(state, ensure_ascii=False)


def parse_gemini_answers(
    data: Any, questions: dict[str, dict[str, Any]], fallback_model: str
) -> JevResult:
    """Validate a Decisions API reply into the same JevResult shape Jev returns.

    The reply is typed already — no JSON is parsed out of prose, so there is
    no repair attempt: a malformed answer raises and the pipeline treats the
    paper as failed (and quarantines it after repeated failures), the same
    as a malformed Jev reply. The numbers that survive are Gemini Decision
    1's own probabilities, calibrated per Google's claim — not a measurement
    on your data; see the module docstring.
    """
    if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
        raise JevError("Malformed Gemini response: missing 'answers'")
    answers = data["answers"]
    out: dict[str, dict[str, Any]] = {}
    for key, question in questions.items():
        answer = answers.get(key)
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise JevError(f"Malformed Gemini response: answer {key!r} missing or wrong type")
        kind = question["type"]
        if kind == "noul":
            value = answer.get("noul")
            if not _is_number(value) or not 0 <= value <= 1:
                raise JevError(f"Malformed Gemini response: {key!r} noul must be a number in [0, 1]")
            out[key] = {"type": "noul", "noul": round(float(value), 4)}
            if _is_number(answer.get("confidence")):
                out[key]["confidence"] = round(float(answer["confidence"]), 4)
        elif kind == "choice":
            value = answer.get("choice")
            criteria = question["criteria"]
            if not isinstance(value, str) or value not in criteria:
                raise JevError(f"Malformed Gemini response: {key!r} choice must be one of {sorted(criteria)}")
            out[key] = {"type": "choice", "choice": value}
            probs = answer.get("probabilities")
            if isinstance(probs, dict):
                out[key]["probabilities"] = {k: round(float(v), 4) for k, v in probs.items() if _is_number(v)}
            if _is_number(answer.get("confidence")):
                out[key]["confidence"] = round(float(answer["confidence"]), 4)
        elif kind == "score":
            value = answer.get("score")
            levels = list(question["criteria"])
            if not _is_number(value) or not 0 <= value <= len(levels) - 1:
                raise JevError(
                    f"Malformed Gemini response: {key!r} score must be a number in [0, {len(levels) - 1}]"
                )
            out[key] = {
                "type": "score",
                "score": round(float(value), 3),
                "legend": {str(i): level for i, level in enumerate(levels)},
            }
            probs = answer.get("probabilities")
            if isinstance(probs, dict):
                out[key]["probabilities"] = {k: round(float(v), 4) for k, v in probs.items() if _is_number(v)}
            if _is_number(answer.get("confidence")):
                out[key]["confidence"] = round(float(answer["confidence"]), 4)
        else:
            raise JevError(f"Malformed Gemini response: unknown question type {kind!r} for {key!r}")
    usage = data.get("usage") or {}
    total_in = usage.get("total_input_tokens")
    return JevResult(
        answers=out,
        model=str(data.get("model") or fallback_model),
        input_tokens=int(total_in) if isinstance(total_in, int) and not isinstance(total_in, bool) else 0,
        cost=None,  # The API bills input only; the pipeline estimates from price_per_mtok.
    )


class GeminiBackend:
    """Gemini Decision 1 as the judge, via the Decisions API (stdlib urllib only).

    One call per paper, same question shape as Jev — the Decisions API
    copied Jev's three types, so the pipeline's question dicts go across
    almost verbatim (only a noul's true/false descriptions are renamed).
    The key is read from GEMINI_API_KEY at runtime and is never stored
    anywhere by this code. Get one at Google AI Studio; the no-cost tier
    covers prototyping, and the paid tier bills $0.10 per million input
    tokens with $0 output.

    Differences from the Jev backends, stated plainly: the calibration is
    Google's claim (lowest calibration error on its own benchmark suite),
    not a measurement on your data — run ``paper-radar calibrate`` on your
    own labels before trusting the thresholds; and noul is clamped to
    [0.01, 0.99], so the model never claims certainty. There is no repair
    attempt: the reply is typed, not prose, so a malformed answer is a
    failure, and the pipeline quarantines the paper after repeated failures
    instead of retrying it every day.
    """

    name = "gemini"

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        timeout: float,
        max_retries: int,
        limiter: RateLimiter,
    ):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = limiter
        self._headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    def decide(self, state: Any, questions: dict[str, dict[str, Any]]) -> JevResult:
        records: list[dict[str, Any]] = []
        try:
            result = self._decide(state, questions, records)
        except JevError as error:
            error.request_usage = records or [response_usage({})]
            raise
        result.request_usage = records
        result.input_tokens = sum(r.get("input_tokens") or 0 for r in records)
        return result

    def _decide(self, state: Any, questions: dict[str, dict[str, Any]], records: list[dict[str, Any]]) -> JevResult:
        body = json.dumps(
            {
                "model": self.model,
                "input": _gemini_input_text(state),
                "questions": _gemini_questions(questions),
            }
        ).encode("utf-8")
        attempt = 0
        while True:
            self.limiter.acquire()
            request = urllib.request.Request(self.url, data=body, method="POST", headers=self._headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
            except urllib.error.HTTPError as error:
                records.append(response_usage({}))
                detail = error.read()[:300].decode("utf-8", errors="replace")
                message = f"{self.name} HTTP {error.code}: {detail}"
                if error.code in FATAL_STATUSES:
                    raise JevError(message, fatal=True, status=error.code) from None
                if error.code not in RETRYABLE_STATUSES or attempt >= self.max_retries:
                    raise JevError(message, status=error.code) from None
                delay = _retry_after(error.headers) or _backoff(attempt)
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as error:
                records.append(response_usage({}))
                if attempt >= self.max_retries:
                    raise JevError(f"{self.name} request failed: {error}") from None
                delay = _backoff(attempt)
            else:
                # Record usage before validating: a malformed reply is still billed.
                usage = data.get("usage") if isinstance(data, dict) else None
                total_in = usage.get("total_input_tokens") if isinstance(usage, dict) else None
                records.append(
                    response_usage(
                        {
                            "model": (data.get("model") if isinstance(data, dict) else None) or self.model,
                            "usage": {"input_tokens": total_in, "output_tokens": 0},
                        }
                    )
                )
                return parse_gemini_answers(data, questions, self.model)
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
        if backend == "claude":
            hint = (
                "Create one at console.anthropic.com (Settings -> API Keys) and set it as "
                "ANTHROPIC_API_KEY — as a repository secret (Settings -> Secrets and variables -> Actions) "
                "or in a local .env file. The API is billed separately from a Claude Pro/Max subscription."
            )
        elif backend == "gemini":
            hint = (
                "Create one at Google AI Studio (aistudio.google.com) and set it as "
                "GEMINI_API_KEY — as a repository secret (Settings -> Secrets and variables -> Actions) "
                "or in a local .env file. The no-cost tier covers prototyping; the paid tier bills "
                "$0.10 per million input tokens with $0 output."
            )
        else:
            hint = (
                "Set it as a repository secret (Settings -> Secrets and variables -> Actions) or export it locally. "
                "No TypeSafe access yet? Use backend = \"openrouter\" (no waitlist) or run `paper-radar demo`."
            )
        raise JevError(f"{key_name} is not set. {hint}", fatal=True)

    limiter = RateLimiter(settings.requests_per_minute)
    if backend == "claude":
        return ClaudeBackend(
            url=settings.base_url or ANTHROPIC_URL,
            api_key=api_key,
            model=model,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            limiter=limiter,
            effort=CLAUDE_DEFAULT_EFFORT if settings.effort is None else settings.effort,
            batch_poll_seconds=settings.batch_poll_seconds,
            batch_timeout_minutes=settings.batch_timeout_minutes,
        )
    if backend == "gemini":
        return GeminiBackend(
            url=settings.base_url or GEMINI_URL,
            api_key=api_key,
            model=model,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            limiter=limiter,
        )
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
