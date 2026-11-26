"""Durable mastery needs evidence from more than one sitting: answers in one session never establish it."""
from datetime import datetime, timedelta, timezone

import pytest

from backend import mastery_model

pytestmark = pytest.mark.prereqai
T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
ANSWERS = [(True, "high", "q1"), (True, "high", "q2"), (True, "high", "q1"), (True, "high", "q2")]


def at(*hours):
    return [T0 + timedelta(hours=h) for h in hours]


def test_four_correct_answers_in_one_moment_are_not_durable_mastery():
    result = mastery_model.estimate(ANSWERS, at(0, 0, 0, 0))
    assert result["p"] > 0.95 and result["mastered"] is False and result["spaced_blocks"] == 1
    assert "block" in result["reason"] and "another day" in result["reason"]


def test_answers_over_a_few_minutes_are_still_one_block():
    assert mastery_model.estimate(ANSWERS, at(0, 0.1, 0.2, 5))["mastered"] is False


def test_answers_on_two_different_days_establish_mastery():
    result = mastery_model.estimate(ANSWERS, at(0, 0.1, 30, 30.1))
    assert result["mastered"] is True and result["spaced_blocks"] == 2


def test_the_spacing_boundary_is_exactly_twelve_hours():
    assert mastery_model.estimate(ANSWERS, at(0, 0, 11.99, 11.99))["mastered"] is False
    assert mastery_model.estimate(ANSWERS, at(0, 0, 12, 12))["mastered"] is True


def test_repeating_one_question_across_days_is_not_enough_without_a_second_question():
    same = [(True, "high", "q1")] * 4
    assert mastery_model.estimate(same, at(0, 30, 60, 90))["mastered"] is False


def test_without_any_known_time_the_rule_is_not_applied():
    assert mastery_model.estimate(ANSWERS)["mastered"] is True
    assert mastery_model.estimate(ANSWERS, [None] * 4)["mastered"] is True


def test_answers_of_unknown_time_share_the_earliest_known_block():
    result = mastery_model.estimate(ANSWERS, [None, None, T0, T0])  # earlier this counted the untimed answers as a separate sitting and declared mastery from one
    assert result["mastered"] is False and result["spaced_blocks"] == 1
    assert mastery_model.estimate(ANSWERS, [None, None, T0, T0 + timedelta(days=2)])["mastered"] is True
    assert mastery_model.spaced_blocks([None, None]) == 1 and mastery_model.spaced_blocks([]) == 0


def test_a_profile_with_same_session_history_is_not_mastered_but_a_spaced_one_is():
    def entry(question, codes):
        return {"graded_attempts": len(codes), "graded_correct": len(codes), "graded_streak": len(codes), "graded_history": codes}

    cram = [("q1", entry("q1", ["1h@2026-11-20T09:00:00Z", "1h@2026-11-20T09:05:00Z"])), ("q2", entry("q2", ["1h@2026-11-20T09:10:00Z", "1h@2026-11-20T09:15:00Z"]))]
    spaced = [("q1", entry("q1", ["1h@2026-11-20T09:00:00Z", "1h@2026-11-22T09:05:00Z"])), ("q2", entry("q2", ["1h@2026-11-20T09:10:00Z", "1h@2026-11-22T09:15:00Z"]))]
    assert mastery_model.estimate_entries(cram)["mastered"] is False
    assert mastery_model.estimate_entries(spaced)["mastered"] is True


def test_a_concept_held_back_only_by_spacing_says_when_another_answer_will_count():
    result = mastery_model.estimate(ANSWERS, at(0, 1, 2, 3))
    assert result["mastered"] is False and result["spacing_ready_at"] == "2026-11-20T21:00:00Z"
    assert "from 2026-11-20 21:00 UTC" in result["reason"]
    assert "spacing_ready_at" not in mastery_model.estimate(ANSWERS, at(0, 0, 30, 30)) and mastery_model.estimate(ANSWERS)["mastered"]


def test_the_profile_mastery_item_and_the_command_line_show_the_spacing(tmp_path):
    from backend import learner_profile

    path = tmp_path / "p.json"
    for question in ("Calculus:1", "Calculus:2"):
        for minutes in (0, 5):
            learner_profile.record_quiz(path, question, "Calculus", "knew", moment=T0 + timedelta(minutes=minutes), graded={"correct": True, "confidence": "high"})
    item = learner_profile.mastery(learner_profile.load_full(path)[0]["quiz"], now=T0 + timedelta(hours=2))[0]
    assert item["status"] == "progressing" and item["spaced_blocks"] == 1 and item["spacing_ready_at"] == "2026-11-20T21:00:00Z"
    assert "another day" in learner_profile.describe_mastery(item) and "21:00 UTC" in learner_profile.describe_mastery(item)


def test_answers_that_rolled_out_of_the_history_do_not_make_a_second_block():
    from backend import spaced_review

    entry = None
    for minute in range(30):  # thirty correct answers in one sitting: ten of them roll out of the 20 kept
        entry = spaced_review.update(entry, "Softmax", "knew", T0 + timedelta(minutes=minute), {"correct": True, "confidence": "high"})
    assert entry["graded_attempts"] == 30 and len(entry["graded_history"]) == spaced_review.HISTORY_LIMIT
    assert entry["graded_first_at"] == spaced_review.stamp(T0)
    result = mastery_model.estimate_entries([("Softmax:1", entry), ("Softmax:2", entry)])
    assert result["spaced_blocks"] == 1 and result["mastered"] is False


def test_untimed_older_answers_share_the_earliest_known_block_instead_of_being_one_of_their_own():
    assert mastery_model.spaced_blocks([None] * 10 + at(*[i / 60 for i in range(20)])) == 1
    assert mastery_model.spaced_blocks([None, None]) == 1 and mastery_model.spaced_blocks([]) == 0
    entry = {"graded_attempts": 25, "graded_correct": 25, "graded_history": [f"1h@{(T0 + timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ')}" for i in range(20)]}  # a legacy entry with no graded_first_at
    assert mastery_model.estimate_entries([("q", entry)])["mastered"] is False


def test_a_real_earlier_sitting_recorded_in_graded_first_at_still_counts_as_a_second_block():
    from backend import spaced_review

    entry = None
    entry = spaced_review.update(entry, "Softmax", "knew", T0, {"correct": True, "confidence": "high"})
    for minute in range(25):
        entry = spaced_review.update(entry, "Softmax", "knew", T0 + timedelta(days=3, minutes=minute), {"correct": True, "confidence": "high"})
    assert entry["graded_first_at"] == spaced_review.stamp(T0)
    result = mastery_model.estimate_entries([("Softmax:1", entry), ("Softmax:2", entry)])
    assert result["spaced_blocks"] == 2 and result["mastered"] is True


def test_a_profile_with_graded_first_at_loads_and_a_malformed_one_is_refused(tmp_path):
    import json

    from backend import learner_profile, spaced_review

    entry = spaced_review.update(None, "Softmax", "knew", T0, {"correct": True, "confidence": "high"})
    quiz = {"Softmax:1": {**entry}}
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"format": "prereqai-learner-profile", "schema_version": 3, "known": [], "studied": [], "quiz": quiz}))
    assert learner_profile.load_full(path)[0]["quiz"]["Softmax:1"]["graded_first_at"] == spaced_review.stamp(T0)
    quiz["Softmax:1"]["graded_first_at"] = "yesterday-ish"
    path.write_text(json.dumps({"format": "prereqai-learner-profile", "schema_version": 3, "known": [], "studied": [], "quiz": quiz}))
    profile, problem = learner_profile.load_full(path)
    assert profile["quiz"] == {} and "invalid entry" in problem
