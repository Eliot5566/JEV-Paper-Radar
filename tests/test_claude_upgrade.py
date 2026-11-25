"""Claude backend: effort, caching layout, refusals and the Message Batches path.

Everything runs against a local fake of the Anthropic API (POST and GET), with
a dummy key; no network.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from paper_radar.config import ConfigError, JevSettings, parse_config
from paper_radar.jev import ClaudeBackend, JevError, claude_output_schema, make_backend
from paper_radar.models import JevResult
from paper_radar.usage import summarize_usage

QUESTIONS = {
    "i_a": {"type": "noul", "instructions": "About agents"},
    "s_paper_type": {"type": "choice", "instructions": "Type?", "criteria": {"benchmark": "b", "survey": "s"}},
    "s_evidence": {"type": "score", "instructions": "Evidence", "criteria": ["none", "some", "lots"]},
}
GOOD = {"i_a": 0.9, "s_paper_type": "survey", "s_evidence": 1}


def _message(answers, *, stop="end_turn", usage=None):
    return {
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "stop_reason": stop,
        "content": [{"type": "text", "text": json.dumps(answers)}] if answers is not None else [],
        "usage": usage or {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 400,
                           "cache_creation_input_tokens": 0},
    }


class FakeAnthropic:
    """Routes: POST /v1/messages, POST /v1/messages/batches, GET /v1/messages/batches/<id>,
    POST .../cancel, GET /results. Each route takes a list of replies (the last repeats)."""

    def __init__(self, routes):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                outer.requests.append({"method": method, "path": self.path, "body": body})
                key = f"{method} {self.path}"
                queue = outer.routes.get(key)
                if not queue:
                    self.send_response(404)
                    self.end_headers()
                    return
                status, payload = queue.pop(0) if len(queue) > 1 else queue[0]
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                data = payload if isinstance(payload, str) else json.dumps(payload)
                self.wfile.write(data.encode())

            def do_POST(self):  # noqa: N802
                self._reply("POST")

            def do_GET(self):  # noqa: N802
                self._reply("GET")

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def fake():
    made = []

    def make(routes):
        server = FakeAnthropic(routes)
        made.append(server)
        return server

    yield make
    for server in made:
        server.close()


def _backend(url, **settings):
    base = dict(backend="claude", base_url=url + "/v1/messages", max_retries=1, requests_per_minute=6000)
    base.update(settings)
    backend = make_backend(JevSettings(**base), env={"ANTHROPIC_API_KEY": "sk-ant-test"})
    assert isinstance(backend, ClaudeBackend)
    backend._sleep = lambda seconds: None  # no real waiting in tests
    return backend


def _jsonl(rows):
    return "\n".join(json.dumps(r) for r in rows) + "\n"


# ------------------------------------------------------------------ single calls


def test_effort_setting_and_empty_effort(fake):
    server = fake({"POST /v1/messages": [(200, _message(GOOD))]})
    _backend(server.url, effort="medium").decide({"title": "T"}, QUESTIONS)
    _backend(server.url, effort="").decide({"title": "T"}, QUESTIONS)
    assert server.requests[0]["body"]["output_config"]["effort"] == "medium"
    assert "effort" not in server.requests[1]["body"]["output_config"]


def test_system_prefix_is_identical_across_papers(fake):
    server = fake({"POST /v1/messages": [(200, _message(GOOD))]})
    backend = _backend(server.url)
    backend.decide({"title": "One", "abstract": "a"}, QUESTIONS)
    backend.decide({"title": "Two", "abstract": "b"}, dict(reversed(list(QUESTIONS.items()))))
    first, second = (r["body"] for r in server.requests)
    # Same bytes in the cached prefix even when the dict order differs.
    assert first["system"] == second["system"]
    assert first["messages"] != second["messages"]


def test_refusal_is_not_repaired(fake):
    server = fake({"POST /v1/messages": [(200, _message(None, stop="refusal"))]})
    with pytest.raises(JevError, match="refusal"):
        _backend(server.url).decide({"title": "T"}, QUESTIONS)
    assert len(server.requests) == 1


def test_out_of_range_noul_still_repaired(fake):
    server = fake({"POST /v1/messages": [(200, _message({**GOOD, "i_a": 85})), (200, _message(GOOD))]})
    result = _backend(server.url).decide({"title": "T"}, QUESTIONS)
    assert result.answers["i_a"]["noul"] == 0.9 and len(server.requests) == 2
    assert server.requests[1]["body"]["messages"][-1]["role"] == "user"


def test_output_schema_shapes():
    schema = claude_output_schema(QUESTIONS)
    assert schema["properties"]["i_a"]["type"] == "number"
    assert schema["properties"]["s_evidence"]["type"] == "number"
    assert "minimum" not in json.dumps(schema)  # unsupported by structured outputs


# ------------------------------------------------------------------ batches

STATES = [{"title": f"P{i}", "abstract": "x"} for i in range(3)]


def _batch_routes(results, *, status_sequence=None, url=""):
    ended = {"id": "msgbatch_1", "processing_status": "ended", "results_url": url + "/results"}
    statuses = status_sequence or [ended]
    return {
        "POST /v1/messages/batches": [(200, {"id": "msgbatch_1", "processing_status": "in_progress"})],
        "GET /v1/messages/batches/msgbatch_1": [(200, s) for s in statuses],
        "GET /results": [(200, _jsonl(results))],
        "POST /v1/messages": [(200, _message(GOOD))],
        "POST /v1/messages/batches/msgbatch_1/cancel": [(200, {"id": "msgbatch_1", "processing_status": "canceling"})],
    }


def test_batch_happy_path_in_order(fake):
    server = fake({})
    results = [
        {"custom_id": "p2", "result": {"type": "succeeded", "message": _message({**GOOD, "i_a": 0.2})}},
        {"custom_id": "p0", "result": {"type": "succeeded", "message": _message({**GOOD, "i_a": 0.0})}},
        {"custom_id": "p1", "result": {"type": "succeeded", "message": _message({**GOOD, "i_a": 0.1})}},
    ]
    server.routes = _batch_routes(results, url=server.url)
    outcomes = _backend(server.url).decide_batch(STATES, QUESTIONS, log=lambda m: None)
    assert [o.answers["i_a"]["noul"] for o in outcomes] == [0.0, 0.1, 0.2]
    create = server.requests[0]["body"]["requests"]
    assert [r["custom_id"] for r in create] == ["p0", "p1", "p2"]
    assert create[0]["params"]["output_config"]["effort"] == "low"
    assert all(o.request_usage[0]["batch"] is True for o in outcomes)
    assert not any(r["path"] == "/v1/messages" for r in server.requests)


def test_batch_falls_back_for_malformed_errored_and_missing(fake):
    server = fake({})
    results = [
        {"custom_id": "p0", "result": {"type": "succeeded", "message": _message({**GOOD, "i_a": 7})}},
        {"custom_id": "p1", "result": {"type": "errored", "error": {"type": "overloaded_error"}}},
        # p2 missing (expired or dropped)
    ]
    server.routes = _batch_routes(results, url=server.url)
    outcomes = _backend(server.url).decide_batch(STATES, QUESTIONS, log=lambda m: None)
    assert all(isinstance(o, JevResult) for o in outcomes)
    direct = [r for r in server.requests if r["path"] == "/v1/messages"]
    assert len(direct) == 3
    # p0's repair turn echoes the batch answer back instead of asking from scratch.
    assert direct[0]["body"]["messages"][1]["role"] == "assistant"
    # p0 keeps the billed batch record plus its repair call.
    assert outcomes[0].request_usage[0]["batch"] is True and len(outcomes[0].request_usage) == 2


def test_batch_timeout_cancels_and_judges_one_by_one(fake):
    server = fake({})
    server.routes = _batch_routes([], status_sequence=[{"id": "msgbatch_1", "processing_status": "in_progress"}], url=server.url)
    backend = _backend(server.url, batch_timeout_minutes=1)
    backend.batch_timeout_minutes = 0  # already past the deadline
    outcomes = backend.decide_batch(STATES, QUESTIONS, log=lambda m: None)
    assert all(isinstance(o, JevResult) for o in outcomes)
    assert any(r["path"].endswith("/cancel") for r in server.requests)


def test_batch_fatal_create_raises(fake):
    server = fake({"POST /v1/messages/batches": [(401, {"error": "bad key"})]})
    with pytest.raises(JevError) as caught:
        _backend(server.url).decide_batch(STATES, QUESTIONS, log=lambda m: None)
    assert caught.value.fatal


def test_batch_discount_in_cost_estimate():
    settings = JevSettings(backend="claude", price_per_mtok=0.10, output_price_per_mtok=0.50,
                           cache_read_price_per_mtok=0.01, cache_creation_price_per_mtok=0.125)
    record = {"model": "m", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_input_tokens": 0,
              "cache_creation_input_tokens": 0, "reported_cost_usd": None}
    full = summarize_usage([record], settings)["cost_usd"]
    half = summarize_usage([{**record, "batch": True}], settings)["cost_usd"]
    assert full == pytest.approx(0.10) and half == pytest.approx(0.05)


# ------------------------------------------------------------------ pipeline + config


def test_pipeline_uses_batch_when_enabled(fake, tmp_path):
    from paper_radar.models import Paper
    from paper_radar.pipeline import judge_all

    server = fake({})
    results = [{"custom_id": f"p{i}", "result": {"type": "succeeded", "message": _message(GOOD)}} for i in range(2)]
    server.routes = _batch_routes(results, url=server.url)
    config = parse_config({
        "jev": {"backend": "claude", "batch": True, "base_url": server.url + "/v1/messages"},
        "sources": [{"type": "arxiv", "categories": ["cs.AI"]}], "interests": [{"id": "a", "label": "A", "text": "About agents"}],
    })
    backend = _backend(server.url, batch=True)
    papers = [Paper(id=f"arxiv:{i}", source="arxiv", title=f"T{i}", abstract="x", url="u") for i in range(2)]
    seen = []

    def verdict(paper, result, cfg):
        seen.append(paper.id)
        return paper.id

    usage = []
    decisions, failures = judge_all(backend, papers, QUESTIONS, config, log=lambda m: None, verdict=verdict, usage=usage)
    assert sorted(decisions) == ["arxiv:0", "arxiv:1"] and not failures
    assert len(usage) == 2 and all(r["batch"] for r in usage)


@pytest.mark.parametrize(
    "jev, message",
    [
        ({"backend": "claude", "effort": "extreme"}, "jev.effort must be"),
        ({"backend": "typesafe", "effort": "low"}, "only applies"),
        ({"backend": "typesafe", "batch": True}, "only applies"),
        ({"backend": "claude", "batch_timeout_minutes": 0}, "batch_timeout_minutes"),
    ],
)
def test_config_validation(jev, message):
    with pytest.raises(ConfigError, match=message):
        parse_config({"jev": jev, "sources": [{"type": "arxiv", "categories": ["cs.AI"]}], "interests": [{"id": "a", "label": "A", "text": "About agents"}]})
