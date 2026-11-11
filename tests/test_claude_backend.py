"""The Claude backend against a local fake of the Anthropic Messages API.

No network and no real key: the key used here is a dummy string, and every
response comes from a local HTTP server. See tests/test_jev_http.py for the
same pattern used for the Jev backends.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from paper_radar.config import JevSettings
from paper_radar.jev import (
    ClaudeBackend,
    JevError,
    make_backend,
    parse_claude_answers,
)

QUESTIONS = {
    "i_a": {"type": "noul", "instructions": "About agents"},
    "s_paper_type": {"type": "choice", "instructions": "Type?", "criteria": {"benchmark": "b", "survey": "s"}},
    "s_evidence": {"type": "score", "instructions": "Evidence", "criteria": ["none", "some", "lots"]},
}

GOOD_ANSWERS = {"i_a": 0.93, "s_paper_type": "benchmark", "s_evidence": 1.4}


def _claude_response(answers, model="claude-haiku-5-5"):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": json.dumps(answers)}],
        "model": model,
        "usage": {"input_tokens": 612, "output_tokens": 40},
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
    env = {"ANTHROPIC_API_KEY": "sk-ant-test"}
    # Point at the fake server's /v1/messages path, as the real URL does.
    settings = JevSettings(backend="claude", base_url=url + "/v1/messages", max_retries=retries, requests_per_minute=6000)
    backend = make_backend(settings, env=env)
    assert isinstance(backend, ClaudeBackend)
    return backend


def test_request_shape_and_parse(server_factory):
    server = server_factory([(200, {}, _claude_response(GOOD_ANSWERS))])
    result = _backend(server.url).decide({"title": "T", "abstract": "A"}, QUESTIONS)
    req = server.requests[0]
    assert req["path"] == "/v1/messages"
    headers = {k.lower(): v for k, v in req["headers"].items()}
    assert headers["x-api-key"] == "sk-ant-test"
    assert headers["anthropic-version"] == "2023-06-01"
    body = req["body"]
    assert body["model"] == "claude-haiku-5-5"
    assert body["temperature"] == 0
    assert body["max_tokens"] == 1024
    # No assistant prefill: Haiku 5.5 rejects it, so the last message is the user turn.
    assert body["messages"][-1]["role"] == "user"
    assert "i_a" in body["messages"][-1]["content"]
    assert result.answers["i_a"] == {"type": "noul", "noul": 0.93}
    assert result.answers["s_paper_type"] == {"type": "choice", "choice": "benchmark"}
    assert result.answers["s_evidence"]["score"] == 1.4
    assert result.answers["s_evidence"]["legend"] == {"0": "none", "1": "some", "2": "lots"}
    assert result.input_tokens == 612 and result.model == "claude-haiku-5-5" and result.cost is None


def test_fenced_json_is_accepted(server_factory):
    text = "```json\n" + json.dumps(GOOD_ANSWERS) + "\n```"
    server = server_factory([(200, {}, _claude_response(GOOD_ANSWERS) | {"content": [{"type": "text", "text": text}]} )])
    result = _backend(server.url).decide({"title": "T", "abstract": "A"}, QUESTIONS)
    assert result.answers["i_a"]["noul"] == 0.93


def test_retries_429_then_succeeds(server_factory):
    server = server_factory(
        [(429, {"retry-after": "0.01"}, {"error": "slow down"}), (200, {}, _claude_response(GOOD_ANSWERS))]
    )
    result = _backend(server.url).decide("state", QUESTIONS)
    assert len(server.requests) == 2 and result.answers["i_a"]["noul"] == 0.93


def test_auth_error_is_fatal_and_not_retried(server_factory):
    server = server_factory([(401, {}, {"error": {"type": "authentication_error", "message": "bad key"}})])
    with pytest.raises(JevError) as info:
        _backend(server.url).decide("state", QUESTIONS)
    assert info.value.fatal and info.value.status == 401 and len(server.requests) == 1


def test_malformed_json_raises(server_factory):
    bad = _claude_response(GOOD_ANSWERS)
    bad["content"] = [{"type": "text", "text": "not json at all"}]
    server = server_factory([(200, {}, bad)])
    with pytest.raises(JevError, match="not valid JSON"):
        _backend(server.url).decide("state", QUESTIONS)


def test_missing_text_content_raises(server_factory):
    bad = _claude_response(GOOD_ANSWERS)
    bad["content"] = []
    server = server_factory([(200, {}, bad)])
    with pytest.raises(JevError, match="no text content"):
        _backend(server.url).decide("state", QUESTIONS)


@pytest.mark.parametrize(
    "answers",
    [
        {**GOOD_ANSWERS, "i_a": 1.5},  # probability outside [0, 1]
        {**GOOD_ANSWERS, "i_a": "high"},  # not a number
        {**GOOD_ANSWERS, "s_paper_type": "novel"},  # not one of the criteria
        {**GOOD_ANSWERS, "s_evidence": 9},  # score outside [0, len(criteria) - 1]
        {"i_a": 0.5},  # missing keys
    ],
)
def test_invalid_answers_rejected(answers):
    with pytest.raises(JevError):
        parse_claude_answers(answers, QUESTIONS, "claude-haiku-5-5")


def test_missing_key_message():
    with pytest.raises(JevError, match="ANTHROPIC_API_KEY is not set"):
        make_backend(JevSettings(backend="claude"), env={})


def test_claude_defaults():
    backend = make_backend(JevSettings(backend="claude"), env={"ANTHROPIC_API_KEY": "k"})
    assert isinstance(backend, ClaudeBackend)
    assert backend.model == "claude-haiku-5-5"
    assert backend.url == "https://api.anthropic.com/v1/messages"
