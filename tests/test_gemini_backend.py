"""The Gemini backend against a local fake of the Decisions API.

No network and no real key: the key used here is a dummy string, and every
response comes from a local HTTP server. See tests/test_claude_backend.py
for the same pattern used for the Claude backend. The fake reply follows
the shape of a real Decisions API reply observed on 2026-11-13 (answers
keyed by question, usage with total_input_tokens / total_output_tokens).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from paper_radar.config import JevSettings
from paper_radar.jev import (
    GeminiBackend,
    JevError,
    _gemini_questions,
    make_backend,
    parse_gemini_answers,
)

QUESTIONS = {
    "i_a": {
        "type": "noul",
        "instructions": "About agents",
        "criteria": {"true": "It is about agents.", "false": "It is not about agents."},
    },
    "s_paper_type": {"type": "choice", "instructions": "Type?", "criteria": {"benchmark": "b", "survey": "s"}},
    "s_evidence": {"type": "score", "instructions": "Evidence", "criteria": ["none", "some", "lots"]},
}

GOOD_ANSWERS = {
    "i_a": {"type": "noul", "noul": 0.93, "confidence": 0.93},
    "s_paper_type": {
        "type": "choice",
        "choice": "benchmark",
        "probabilities": {"benchmark": 0.91, "survey": 0.09},
        "confidence": 0.91,
    },
    "s_evidence": {
        "type": "score",
        "score": 1.4,
        "probabilities": {"0": 0.1, "1": 0.4, "2": 0.5},
        "legend": {"0": "none", "1": "some", "2": "lots"},
        "confidence": 0.5,
    },
}


def _gemini_response(answers):
    # The real reply carries no top-level "model": the fallback model is used.
    return {
        "answers": answers,
        "usage": {"total_tokens": 208, "total_input_tokens": 208, "total_output_tokens": 0},
    }


class FakeServer:
    def __init__(self, script):
        self.script = list(script)  # list of (status, headers, body)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers["Content-Length"])
                outer.requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(self.rfile.read(length))})
                status, headers, body = outer.script.pop(0) if len(outer.script) > 1 else outer.script[0]
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server_factory():
    servers = []

    def make(script):
        server = FakeServer(script)
        servers.append(server)
        return server

    yield make
    for s in servers:
        s.close()


def _backend(url, retries=3):
    env = {"GEMINI_API_KEY": "test-key"}
    # Point at the fake server's /v1beta/decisions path, as the real URL does.
    settings = JevSettings(backend="gemini", base_url=url + "/v1beta/decisions", max_retries=retries, requests_per_minute=6000)
    backend = make_backend(settings, env=env)
    assert isinstance(backend, GeminiBackend)
    return backend


def test_request_shape_and_parse(server_factory):
    server = server_factory([(200, {}, _gemini_response(GOOD_ANSWERS))])
    result = _backend(server.url).decide({"title": "T", "abstract": "A"}, QUESTIONS)
    req = server.requests[0]
    assert req["path"] == "/v1beta/decisions"
    headers = {k.lower(): v for k, v in req["headers"].items()}
    assert headers["x-goog-api-key"] == "test-key"
    assert "authorization" not in headers  # the Decisions API takes the key header, not Bearer
    body = req["body"]
    assert body["model"] == "gemini-decision-1"
    assert isinstance(body["input"], str) and "T" in body["input"]
    questions = body["questions"]
    # A noul's true/false descriptions are renamed for the Decisions API.
    assert questions["i_a"]["criteria"] == {
        "true_description": "It is about agents.",
        "false_description": "It is not about agents.",
    }
    assert questions["s_paper_type"]["criteria"] == {"benchmark": "b", "survey": "s"}
    assert questions["s_evidence"]["criteria"] == ["none", "some", "lots"]
    assert result.answers["i_a"] == {"type": "noul", "noul": 0.93, "confidence": 0.93}
    assert result.answers["s_paper_type"]["choice"] == "benchmark"
    assert result.answers["s_paper_type"]["probabilities"] == {"benchmark": 0.91, "survey": 0.09}
    assert result.answers["s_evidence"]["score"] == 1.4
    assert result.answers["s_evidence"]["legend"] == {"0": "none", "1": "some", "2": "lots"}
    assert result.input_tokens == 208 and result.model == "gemini-decision-1" and result.cost is None


def test_noul_without_criteria_sends_none(server_factory):
    questions = {"i_a": {"type": "noul", "instructions": "About agents"}}
    server = server_factory(
        [(200, {}, _gemini_response({"i_a": {"type": "noul", "noul": 0.2, "confidence": 0.8}}))]
    )
    result = _backend(server.url).decide({"title": "T", "abstract": "A"}, questions)
    assert "criteria" not in server.requests[0]["body"]["questions"]["i_a"]
    assert result.answers["i_a"]["noul"] == 0.2


def test_questions_translation():
    translated = _gemini_questions(QUESTIONS)
    assert translated["i_a"] == {
        "type": "noul",
        "instructions": "About agents",
        "criteria": {"true_description": "It is about agents.", "false_description": "It is not about agents."},
    }
    # The caller's dicts are not mutated.
    assert QUESTIONS["i_a"]["criteria"] == {"true": "It is about agents.", "false": "It is not about agents."}


def test_retries_429_then_succeeds(server_factory):
    server = server_factory(
        [(429, {"retry-after": "0.01"}, {"error": "slow down"}), (200, {}, _gemini_response(GOOD_ANSWERS))]
    )
    result = _backend(server.url).decide("state", QUESTIONS)
    assert len(server.requests) == 2 and result.answers["i_a"]["noul"] == 0.93


def test_bad_key_is_fatal_and_not_retried(server_factory):
    # The Gemini API answers an invalid key with 400 API_KEY_INVALID.
    server = server_factory([(400, {}, {"error": {"code": 400, "message": "API key not valid."}})])
    with pytest.raises(JevError) as info:
        _backend(server.url).decide("state", QUESTIONS)
    assert info.value.fatal and info.value.status == 400 and len(server.requests) == 1


def test_malformed_response_raises_without_repair(server_factory):
    # A decision model returns typed answers, not prose: there is no repair
    # attempt, so one bad reply is one request and one failure.
    server = server_factory([(200, {}, {"usage": {"total_input_tokens": 10}})])
    with pytest.raises(JevError, match="missing 'answers'") as caught:
        _backend(server.url).decide("state", QUESTIONS)
    assert len(server.requests) == 1
    # The bad reply was still billed, so its input tokens are recorded.
    assert caught.value.request_usage[0]["input_tokens"] == 10


@pytest.mark.parametrize(
    "answers",
    [
        {**GOOD_ANSWERS, "i_a": {**GOOD_ANSWERS["i_a"], "noul": 1.5}},  # probability outside [0, 1]
        {**GOOD_ANSWERS, "i_a": {**GOOD_ANSWERS["i_a"], "noul": "high"}},  # not a number
        {**GOOD_ANSWERS, "s_paper_type": {**GOOD_ANSWERS["s_paper_type"], "choice": "novel"}},  # not one of the criteria
        {**GOOD_ANSWERS, "s_evidence": {**GOOD_ANSWERS["s_evidence"], "score": 9}},  # score outside [0, len(criteria) - 1]
        {"i_a": GOOD_ANSWERS["i_a"]},  # missing keys
    ],
)
def test_invalid_answers_rejected(answers):
    with pytest.raises(JevError):
        parse_gemini_answers(_gemini_response(answers), QUESTIONS, "gemini-decision-1")


def test_missing_key_message():
    with pytest.raises(JevError, match="GEMINI_API_KEY is not set"):
        make_backend(JevSettings(backend="gemini"), env={})


def test_gemini_defaults():
    backend = make_backend(JevSettings(backend="gemini"), env={"GEMINI_API_KEY": "k"})
    assert isinstance(backend, GeminiBackend)
    assert backend.model == "gemini-decision-1"
    assert backend.url == "https://generativelanguage.googleapis.com/v1beta/decisions"
