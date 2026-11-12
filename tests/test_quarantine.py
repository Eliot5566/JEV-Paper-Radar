"""Papers that fail repeatedly are quarantined instead of retried every run.

Regression test for the 13 papers in the Claude example repo that failed
every day on Claude response-format errors (non-numeric probability, invalid
JSON) — each retry cost tokens and never resolved. The fix has three layers:
tolerant parsing plus a repair attempt in the Claude backend, and quarantine
after three consecutive failures here.
"""

from datetime import date

from paper_radar.jev import JevError, MockBackend
from paper_radar.pipeline import run
from paper_radar.store import Store

DAY = date(2026, 9, 22)


def quiet(_):
    pass


class Stub:
    def __init__(self, paper_id):
        self.id = paper_id


class AlwaysFails(MockBackend):
    def decide(self, state, questions):
        if "TraceGrade" in state["title"]:
            raise JevError("Malformed Claude response: 'agent_eval' noul must be a number in [0, 1]")
        return super().decide(state, questions)


def test_store_quarantine_counts_and_expires(tmp_path):
    store = Store(tmp_path / "data")
    paper = Stub("arxiv:1234.56789")
    assert store.quarantined_ids(DAY) == set()
    store.record_failures("2026-09-22", [(paper, "bad json")])
    store.record_failures("2026-09-23", [(paper, "bad json")])
    assert store.quarantined_ids(date(2026, 9, 23)) == set()
    newly = store.record_failures("2026-09-24", [(paper, "bad json")])
    assert newly == ["arxiv:1234.56789"]
    assert store.quarantined_ids(date(2026, 9, 24)) == {"arxiv:1234.56789"}
    # Still quarantined on the last day of the 30-day window, free after it.
    assert store.quarantined_ids(date(2026, 10, 24)) == {"arxiv:1234.56789"}
    assert store.quarantined_ids(date(2026, 10, 25)) == set()
    # One more failure after expiry re-quarantines it.
    assert store.record_failures("2026-10-25", [(paper, "bad json")]) == ["arxiv:1234.56789"]
    record = store.load_quarantine()["arxiv:1234.56789"]
    assert record["failures"] == 4 and record["first_failed"] == "2026-09-22"


def test_paper_quarantined_after_three_runs(config):
    logs: list[str] = []
    first = run(config, AlwaysFails(), today=DAY, notify=False, log=logs.append)
    assert first.failed == 1 and first.judged == 43
    second = run(config, AlwaysFails(), today=DAY, notify=False, log=logs.append)
    assert second.failed == 1 and second.judged == 0
    third = run(config, AlwaysFails(), today=DAY, notify=False, log=logs.append)
    assert third.failed == 1 and third.judged == 0
    fourth = run(config, AlwaysFails(), today=DAY, notify=False, log=logs.append)
    assert fourth.failed == 0 and fourth.judged == 0
    assert any("quarantined" in line for line in logs)
    records = Store(config.data_path).load_quarantine()
    assert len(records) == 1
    record = next(iter(records.values()))
    assert record["failures"] == 3 and record["quarantined_until"] == "2026-10-22"


def test_rejudge_gives_quarantined_paper_a_fresh_chance(config):
    for _ in range(3):
        run(config, AlwaysFails(), today=DAY, notify=False, log=quiet)
    store = Store(config.data_path)
    assert store.quarantined_ids(DAY)
    paper_id = next(iter(store.load_quarantine()))
    result = run(config, AlwaysFails(), today=DAY, notify=False, log=quiet, rejudge=True)
    assert result.failed == 1 and result.judged == 43
    record = Store(config.data_path).load_quarantine()[paper_id]
    assert record["failures"] == 1  # fresh count, not a fourth strike
    assert Store(config.data_path).quarantined_ids(DAY) == set()
