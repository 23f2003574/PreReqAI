import itertools

import pytest

from backend import mastery_model as m

pytestmark = pytest.mark.prereqai


def _entry(codes):
    return {"graded_attempts": len(codes), "graded_correct": sum(c[0] == "1" for c in codes), "graded_streak": 0, "graded_history": codes, "graded_first_at": codes[0].split("@")[1]}


H1 = ["1m@2026-11-01T00:00:00Z", "0m@2026-11-03T00:00:00Z", "1m@2026-11-05T00:00:00Z"]
H2 = ["0m@2026-11-02T00:00:00Z", "1m@2026-11-04T00:00:00Z", "1m@2026-11-06T00:00:00Z"]


def test_estimate_does_not_depend_on_entry_order():
    entries = [("A:1", _entry(H1)), ("B:1", _entry(H2))]
    results = {m.estimate_entries(list(order))["p"] for order in itertools.permutations(entries)}
    assert len(results) == 1


def test_interleaved_evidence_matches_the_chronological_update():
    got = m.estimate_entries([("A:1", _entry(H1)), ("B:1", _entry(H2))])
    chrono = sorted((c.split("@")[1], c[0] == "1") for c in H1 + H2)
    owner = {c.split("@")[1]: "A:1" for c in H1} | {c.split("@")[1]: "B:1" for c in H2}
    answers = [(ok, "medium", owner[t]) for t, ok in chrono]
    assert got["p"] == m.estimate(answers, [None] * len(answers))["p"]


def test_untimed_profiles_keep_their_existing_order():
    a = {"graded_attempts": 2, "graded_correct": 2, "graded_streak": 2}
    b = {"graded_attempts": 2, "graded_correct": 1, "graded_streak": 0}
    first = m.estimate_entries([("A:1", a), ("B:1", b)])
    answers = m.sequence_from_counters(a, "A:1") + m.sequence_from_counters(b, "B:1")
    assert first["p"] == m.estimate(answers, [None] * 4)["p"]
