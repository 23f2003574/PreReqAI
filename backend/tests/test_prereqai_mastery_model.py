"""The uncertainty-aware mastery estimate: guessing, confident misses, graded-only evidence, profile compatibility, calibration."""
import pytest

from backend import adaptive_plan, learner_profile, mastery_model as m

pytestmark = pytest.mark.prereqai


def answers(*flags, confidence="medium"):
    return [(flag, confidence, f"q{i % 2}") for i, flag in enumerate(flags)]


def test_three_lucky_guesses_are_not_mastery_and_four_answers_on_two_questions_are():
    three, four = m.estimate(answers(True, True, True)), m.estimate(answers(True, True, True, True))
    assert three["mastered"] is False and "at least 4" in three["reason"] and three["p"] > 0.9
    assert four["mastered"] is True and four["low"] >= m.MASTERED_LOWER and four["questions_correct"] == 2


def test_one_question_answered_correctly_many_times_is_practice_not_mastery():
    assert m.estimate([(True, "high", "q1")] * 6)["mastered"] is False


def test_repeated_confident_wrong_answers_lower_the_estimate_more_than_unsure_ones():
    start = m.estimate(answers(True, True))["p"]
    base = answers(True, True)
    sure, unsure = m.estimate(base + [(False, "high", "a"), (False, "high", "b")]), m.estimate(base + [(False, "low", "a"), (False, "low", "b")])
    assert sure["p"] < unsure["p"] < start and sure["p"] < 0.1


def test_recovery_after_confident_misses_needs_more_evidence_than_a_clean_run():
    recovered = m.estimate([(True, "medium", "a"), (True, "medium", "b"), (False, "high", "a"), (False, "high", "b"), (True, "medium", "a"), (True, "medium", "b")])
    assert recovered["mastered"] is False


def test_two_confident_misses_block_mastery_even_after_a_long_recovery():
    run = [(False, "high", "a"), (True, "medium", "a"), (True, "medium", "b"), (True, "medium", "a"), (False, "high", "b")] + [(True, "medium", f"r{n}") for n in range(8)]  # eight different questions: repeats of one question would count for less
    estimate = m.estimate(run)
    assert estimate["p"] > 0.95 and estimate["mastered"] is False and "confidently wrong" in estimate["reason"]


def test_the_estimate_is_deterministic_and_explains_itself():
    first = m.estimate(answers(True, False, True, True))
    assert first == m.estimate(answers(True, False, True, True)) and first["reason"] and 0 <= first["low"] <= first["p"] <= first["high"] <= 1
    assert m.estimate([]) is None


def test_only_graded_attempts_count():
    attempts = [{"question_id": "a", "concept": "X", "outcome": "knew", "graded": False}, {"question_id": "b", "concept": "X", "outcome": "knew", "graded": True, "correct": True, "confidence": "high"}]
    assert m.estimate_attempts(attempts)["answers"] == 1 and m.estimate_attempts(attempts[:1]) is None


def test_counters_of_an_older_profile_rebuild_the_same_kind_of_sequence():
    entry = {"graded_attempts": 3, "graded_correct": 2, "graded_streak": 1, "high_confidence_right": 1, "high_confidence_wrong": 1}
    sequence = m.sequence_from_counters(entry, "q")
    assert [c for c, _, _ in sequence] == [True, False, True] and sequence[1][1] == "high" and m.sequence_from_counters({"attempts": 2, "knew": 2}) == []


def mastery_on_day_3(quiz_history):
    """profile mastery one day after the fixtures' last answers (a forgetting model needs a clock)"""
    from datetime import datetime, timezone
    return learner_profile.mastery(quiz_history, datetime(2026, 11, 3, tzinfo=timezone.utc))


def quiz(*rows):
    return {f"{c}:{n}": {"concept": c, "attempts": a, "knew": k, "missed": a - k, "streak": s, "last_outcome": "knew" if s else "missed", "first_seen": "2026-11-01T00:00:00Z", "last_seen": "2026-11-02T00:00:00Z",
                         **extra} for c, n, a, k, s, extra in rows}


def test_profile_mastery_uses_the_estimate_and_old_profiles_load_unchanged():
    graded = {"graded_attempts": 2, "graded_correct": 2, "graded_streak": 2}
    item = mastery_on_day_3(quiz(("Calculus", 1, 2, 2, 2, graded), ("Calculus", 2, 2, 2, 2, graded)))[0]
    assert item["status"] == "mastered" and item["p_mastery"] >= 0.95 and item["mastery_low"] >= 0.85 and item["mastery_reason"]
    three = mastery_on_day_3(quiz(("Calculus", 1, 2, 2, 2, graded), ("Calculus", 2, 1, 1, 1, {"graded_attempts": 1, "graded_correct": 1, "graded_streak": 1})))[0]
    assert three["status"] == "progressing"
    legacy = mastery_on_day_3(quiz(("Softmax", 1, 2, 2, 2, {}), ("Softmax", 2, 2, 2, 2, {})))[0]
    assert legacy["status"] == "self_reported" and "p_mastery" not in legacy


def test_the_adaptive_plan_compresses_only_when_the_lower_end_is_high_enough():
    good = [{"question_id": f"Calculus:{n}", "concept": "Calculus", "graded": True, "correct": True, "confidence": "medium"} for n in (1, 2, 3, 4)]
    evidence = adaptive_plan.evidence_from_attempts(good)["Calculus"]
    assert evidence["mastery_low"] >= adaptive_plan.COMPRESS_LOWER and adaptive_plan.decide("Calculus", 10, evidence)[0] == "compress"
    assert adaptive_plan.decide("Calculus", 10, {**evidence, "mastery_low": 0.5})[0] == "keep"


def test_calibration_scores_the_stated_confidence_against_outcomes():
    graded = [{"graded": True, "correct": True, "confidence": "high"}, {"graded": True, "correct": False, "confidence": "high"}, {"graded": True, "correct": True, "confidence": "low"}, {"graded": False}]
    report = m.calibration(graded)
    assert report["answers"] == 3 and report["by_confidence"]["high"] == {"answers": 2, "accuracy": 0.5} and 0 < report["brier"] < 1 and m.calibration([]) is None
