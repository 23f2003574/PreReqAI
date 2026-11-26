"""A question answered again is partly remembered: repeats count for less, and one question is worth a bounded amount of independent evidence."""
from datetime import datetime, timedelta, timezone

import pytest

from backend import mastery_model as m

pytestmark = pytest.mark.prereqai
T0 = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)


def over_days(sequence, confidence="medium"):
    answers = [(True, confidence, question) for question in sequence]
    return m.estimate(answers, [T0 + timedelta(days=i) for i in range(len(answers))])


def test_one_question_repeated_across_days_plus_one_other_is_not_durable_mastery():
    for sequence in ("aaab", "aaaab", "aaaaab", "abaaaa"):
        result = over_days(sequence)
        assert result["mastered"] is False and result["effective_answers"] == 2.5, sequence
        assert "repeated" in result["reason"] and "independent" in result["reason"]


def test_four_answers_on_two_questions_and_answers_on_distinct_questions_still_establish_mastery():
    assert over_days("abab")["mastered"] is True and over_days("abab")["effective_answers"] == 3.0
    assert over_days("abcd")["mastered"] is True and over_days("abcd")["effective_answers"] == 4.0


def test_a_repeat_moves_the_estimate_less_than_a_new_question_and_one_question_is_capped():
    repeat, fresh = m.estimate([(True, "medium", "a"), (True, "medium", "a")]), m.estimate([(True, "medium", "a"), (True, "medium", "b")])
    assert PRIOR_SANITY < repeat["p"] < fresh["p"]
    assert m.estimate([(True, "medium", "a")] * 10)["effective_answers"] == m.QUESTION_CAP


PRIOR_SANITY = m.PRIOR


def test_a_repeated_wrong_answer_still_counts_against_the_learner_and_confidence_still_matters():
    sure_right, unsure_right = over_days("abab", "high"), over_days("abab", "low")
    assert sure_right["p"] > unsure_right["p"]
    wrong = m.estimate([(True, "medium", "a"), (True, "medium", "b"), (False, "high", "a")])
    assert wrong["p"] < m.estimate([(True, "medium", "a"), (True, "medium", "b")])["p"]


def test_repeat_discounting_is_applied_per_question_and_does_not_depend_on_when_the_repeat_happened():
    same_day = m.estimate([(True, "medium", "a"), (True, "medium", "a"), (True, "medium", "b"), (True, "medium", "b")])
    assert same_day["effective_answers"] == 3.0 and same_day["questions_correct"] == 2
