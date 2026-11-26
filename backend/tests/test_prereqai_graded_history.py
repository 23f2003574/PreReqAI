"""A profile keeps each question's last graded answers in order with their real confidence, so mastery does not depend on a guessed order or on every low-confidence answer being read as medium."""
import json
from datetime import datetime, timezone

import pytest

from backend import learner_profile, mastery_model, spaced_review

pytestmark = pytest.mark.prereqai
T0 = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)


def answer(entry, correct, confidence="medium", step=0):
    return spaced_review.update(entry, "Softmax", "knew" if correct else "missed", T0.replace(minute=step), {"correct": correct, "confidence": confidence})


def run(answers):
    entry = None
    for step, (correct, confidence) in enumerate(answers):
        entry = answer(entry, correct, confidence, step)
    return entry


def test_each_assessed_answer_is_kept_in_order_with_its_confidence_up_to_the_limit():
    entry = run([(True, "low"), (False, "high"), (True, "medium")])
    assert [c.split("@")[0] for c in entry["graded_history"]] == ["1l", "0h", "1m"] and all("@" in c for c in entry["graded_history"]) and entry["graded_attempts"] == 3
    long = run([(index % 2 == 0, "medium") for index in range(spaced_review.HISTORY_LIMIT + 5)])
    assert len(long["graded_history"]) == spaced_review.HISTORY_LIMIT and long["graded_attempts"] == spaced_review.HISTORY_LIMIT + 5
    last = spaced_review.HISTORY_LIMIT + 4  # the answers alternate, correct on even positions
    assert long["graded_history"][-1].split("@")[0] == ("1m" if last % 2 == 0 else "0m")


def test_a_self_reported_answer_carries_the_history_unchanged_and_starts_none():
    entry = run([(True, "high")])
    again = spaced_review.update(entry, "Softmax", "knew", T0.replace(minute=30))
    assert [c.split("@")[0] for c in again["graded_history"]] == ["1h"] and again["graded_attempts"] == 1
    assert "graded_history" not in spaced_review.update(None, "Softmax", "knew", T0)


def test_the_real_order_of_answers_changes_the_estimate_where_counters_could_not():
    start_wrong = run([(False, "medium"), (True, "medium"), (True, "medium"), (True, "medium"), (True, "medium")])
    end_wrong = run([(True, "medium"), (True, "medium"), (True, "medium"), (True, "medium"), (False, "medium")])
    assert start_wrong["graded_correct"] == end_wrong["graded_correct"] == 4
    # The answers of one entry are all to one question, and repeats of a question are discounted (backend/mastery_model.py), which would make the first answer count most; the order effect itself is
    # checked on different questions, where every answer counts the same.
    def estimate(flags):
        return mastery_model.estimate([(flag, "medium", f"q{n}") for n, flag in enumerate(flags)])["p"]

    assert estimate([False, True, True, True, True]) > estimate([True, True, True, True, False])  # a recovery after a miss is better evidence than a miss after the successes
    assert mastery_model.estimate_entries([("Softmax:1", start_wrong)])["answers"] == 5  # the real order is still read from the entry's history


def test_low_confidence_is_no_longer_read_as_medium():
    low = run([(True, "low")] * 4)
    medium = run([(True, "medium")] * 4)
    assert mastery_model.estimate_entries([("A:1", low)])["p"] < mastery_model.estimate_entries([("A:1", medium)])["p"]  # a correct answer given with low confidence is likelier a guess


def test_an_entry_without_history_is_read_exactly_as_before_and_older_answers_are_rebuilt_before_the_history():
    legacy = {"graded_attempts": 4, "graded_correct": 3, "graded_streak": 2, "high_confidence_right": 1, "high_confidence_wrong": 0}
    assert mastery_model.sequence_from_counters(legacy, "Q") == [(True, "high", "Q"), (False, "medium", "Q"), (True, "medium", "Q"), (True, "medium", "Q")]
    mixed = {**legacy, "graded_attempts": 6, "graded_correct": 5, "graded_history": ["0l", "1m", "1h", "1m"]}  # two older answers (both correct) precede four recorded ones
    sequence = mastery_model.sequence_from_counters(mixed, "Q")
    assert len(sequence) == 6 and [x[:2] for x in sequence[2:]] == [(False, "low"), (True, "medium"), (True, "high"), (True, "medium")] and all(item[0] for item in sequence[:2])


def test_the_history_is_saved_loaded_and_validated(tmp_path):
    path = tmp_path / "me.json"
    learner_profile.save(path, [], [], {})
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew", T0, {"correct": True, "confidence": "low"})
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "missed", T0.replace(minute=5), {"correct": False, "confidence": "high"})
    profile, problem = learner_profile.load_full(path)
    assert not problem and [c.split("@")[0] for c in profile["quiz"]["Softmax:1"]["graded_history"]] == ["1l", "0h"]
    data = json.loads(path.read_text())
    for bad in (["1x"], ["1l"] * (spaced_review.HISTORY_LIMIT + 1), "1l", [1], ["1l", "1l", "1l"]):
        data["quiz"]["Softmax:1"]["graded_history"] = bad
        with pytest.raises(learner_profile.ProfileError):
            learner_profile.parse_full(json.dumps(data).encode())
    data["quiz"]["Softmax:1"].pop("graded_history")
    assert "graded_history" not in learner_profile.parse_full(json.dumps(data).encode())["quiz"]["Softmax:1"]  # a file saved before the history is still read
