"""Reject invalid numeric judgements before they reach ranking or screening."""

import copy

import pytest

from paper_radar.jev import JevError, parse_response
from tests.test_jev_http import GOOD, QUESTIONS


@pytest.mark.parametrize("key,field,values", [
    ("i_a", "noul", [-0.01, 1.01, float("nan"), float("inf"), -float("inf"), True, False, "0.5", None]),
    ("s_evidence", "score", [-0.01, 2.01, float("nan"), float("inf"), -float("inf"), True, False, "1", None]),
])
def test_invalid_numeric_answers_are_rejected(key, field, values):
    for value in values:
        data = copy.deepcopy(GOOD)
        data["answers"][key][field] = value
        with pytest.raises(JevError):
            parse_response(data, QUESTIONS, "test-model")


@pytest.mark.parametrize("key,field,value", [
    ("i_a", "noul", 0), ("i_a", "noul", 1), ("i_a", "noul", 0.5),
    ("s_evidence", "score", 0), ("s_evidence", "score", 2), ("s_evidence", "score", 1.4),
])
def test_valid_boundaries_and_fractional_scores_remain_accepted(key, field, value):
    data = copy.deepcopy(GOOD)
    data["answers"][key][field] = value
    assert parse_response(data, QUESTIONS, "test-model").answers[key][field] == value
