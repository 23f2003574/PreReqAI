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


def test_answers_of_unknown_time_count_as_one_earlier_block():
    assert mastery_model.estimate(ANSWERS, [None, None, T0, T0])["mastered"] is True
    assert mastery_model.spaced_blocks([None, None]) == 1 and mastery_model.spaced_blocks([]) == 0


def test_a_profile_with_same_session_history_is_not_mastered_but_a_spaced_one_is():
    def entry(question, codes):
        return {"graded_attempts": len(codes), "graded_correct": len(codes), "graded_streak": len(codes), "graded_history": codes}

    cram = [("q1", entry("q1", ["1h@2026-11-20T09:00:00Z", "1h@2026-11-20T09:05:00Z"])), ("q2", entry("q2", ["1h@2026-11-20T09:10:00Z", "1h@2026-11-20T09:15:00Z"]))]
    spaced = [("q1", entry("q1", ["1h@2026-11-20T09:00:00Z", "1h@2026-11-22T09:05:00Z"])), ("q2", entry("q2", ["1h@2026-11-20T09:10:00Z", "1h@2026-11-22T09:15:00Z"]))]
    assert mastery_model.estimate_entries(cram)["mastered"] is False
    assert mastery_model.estimate_entries(spaced)["mastered"] is True
