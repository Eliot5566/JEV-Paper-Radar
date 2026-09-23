"""The HTTP backend against a local fake of the System One endpoint."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from paper_radar.config import JevSettings
from paper_radar.jev import HTTPBackend, JevError, MockBackend, RateLimiter, make_backend, parse_response

QUESTIONS = {
    "i_a": {"type": "noul", "instructions": "About agents"},
    "s_paper_type": {"type": "choice", "instructions": "Type?", "criteria": {"benchmark": "b", "survey": "s"}},
    "s_evidence": {"type": "score", "instructions": "Evidence", "criteria": ["none", "some", "lots"]},
}

GOOD = {
    "model": "jev-1.13.0",
    "answers": {
        "i_a": {"type": "noul", "noul": 0.93},
        "s_paper_type": {"type": "choice", "choice": "benchmark", "probabilities": {"benchmark": 0.9, "survey": 0.1}, "confidence": 0.88},
        "s_evidence": {"type": "score", "score": 1.4, "legend": {"0": "none", "1": "some", "2": "lots"},
                       "probabilities": {"0": 0.1, "1": 0.4, "2": 0.5}, "confidence": 0.7},
    },
    "usage": {"input_tokens": 612, "output_tokens": 20},
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
    env = {"TYPESAFE_API_KEY": "sk-test", "TYPESAFE_BASE_URL": url}
    backend = make_backend(JevSettings(backend="typesafe", model="jev-1.13.0", max_retries=retries, requests_per_minute=6000), env=env)
    assert isinstance(backend, HTTPBackend)
    return backend


def test_request_shape_and_parse(server_factory):
    server = server_factory([(200, {}, GOOD)])
    result = _backend(server.url).decide({"title": "T", "abstract": "A"}, QUESTIONS)
    req = server.requests[0]
    assert req["path"] == "/v1/systemone"
    assert req["headers"]["Authorization"] == "Bearer sk-test"
    assert req["body"] == {"model": "jev-1.13.0", "state": {"title": "T", "abstract": "A"}, "questions": QUESTIONS}
    assert result.answers["i_a"]["noul"] == 0.93
    assert result.input_tokens == 612 and result.model == "jev-1.13.0" and result.cost is None


def test_retries_429_then_succeeds(server_factory):
    server = server_factory([(429, {"retry-after-ms": "10"}, {"error": "slow down"}), (529, {"retry-after": "0.01"}, {}), (200, {}, GOOD)])
    result = _backend(server.url).decide("state", QUESTIONS)
    assert len(server.requests) == 3 and result.answers["i_a"]["noul"] == 0.93


def test_gives_up_after_retries(server_factory):
    server = server_factory([(503, {"retry-after-ms": "1"}, {})])
    with pytest.raises(JevError) as info:
        _backend(server.url, retries=2).decide("state", QUESTIONS)
    assert not info.value.fatal and len(server.requests) == 3


def test_auth_error_is_fatal_and_not_retried(server_factory):
    server = server_factory([(401, {}, {"detail": "bad key"})])
    with pytest.raises(JevError) as info:
        _backend(server.url).decide("state", QUESTIONS)
    assert info.value.fatal and info.value.status == 401 and len(server.requests) == 1


def test_openrouter_cost_is_used():
    data = {**GOOD, "usage": {"input_tokens": 476, "output_tokens": 70, "cost": 0.000019992}}
    assert parse_response(data, QUESTIONS, "x").cost == pytest.approx(0.000019992)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["answers"].pop("i_a"),
        lambda d: d["answers"]["s_paper_type"].update(choice="novel"),
        lambda d: d["answers"]["i_a"].update(type="score"),
        lambda d: d.pop("answers"),
    ],
)
def test_malformed_responses_rejected(mutate):
    data = json.loads(json.dumps(GOOD))
    mutate(data)
    with pytest.raises(JevError):
        parse_response(data, QUESTIONS, "x")


def test_missing_key_message():
    with pytest.raises(JevError, match="OPENROUTER_API_KEY is not set"):
        make_backend(JevSettings(backend="openrouter"), env={})


def test_openrouter_defaults():
    backend = make_backend(JevSettings(backend="openrouter"), env={"OPENROUTER_API_KEY": "k"})
    assert backend.url == "https://openrouter.ai/api/alpha/decisions" and backend.model == "typesafe/jev-1.13"


def test_mock_answers_every_question():
    result = MockBackend().decide({"title": "LLM agents", "abstract": "We evaluate agents on tool-use tasks"}, QUESTIONS)
    assert set(result.answers) == set(QUESTIONS)
    parse_response({"answers": result.answers, "usage": {"input_tokens": 1}}, QUESTIONS, "mock")
    assert 0 <= result.answers["i_a"]["noul"] <= 1


def test_rate_limiter_spacing():
    import time

    limiter = RateLimiter(per_minute=1200)  # 50 ms apart
    start = time.monotonic()
    for _ in range(4):
        limiter.acquire()
    assert time.monotonic() - start >= 0.14
