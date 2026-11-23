"""Mastery fades with time without new graded evidence: the probability decays toward the prior by a stated heuristic, recent demonstrations stay recognised, a lapsed concept needs a refresh (and is no longer offered as
"you may already know this") until the learner answers again, and profiles whose answers carry no times still read."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend import curriculum, learner_profile, mastery_model, spaced_review

pytestmark = pytest.mark.prereqai
NOW = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc)


def mastered_quiz(days_ago, concept="Calculus", last_outcome="knew", interval_hours=72.0, timed=False):
    """Two questions answered correctly four times in all (assessed), the last answer `days_ago` days before NOW."""
    seen = spaced_review.stamp(NOW - timedelta(days=days_ago))
    base = {"concept": concept, "attempts": 2, "knew": 2, "missed": 0, "streak": 2, "last_outcome": last_outcome, "first_seen": "2026-10-01T00:00:00Z", "last_seen": seen,
            "interval_hours": interval_hours, "due": spaced_review.stamp(NOW - timedelta(days=days_ago) + timedelta(hours=interval_hours)), "graded_attempts": 2, "graded_correct": 2, "graded_streak": 2}
    if timed:
        base["graded_history"] = [f"1m@{spaced_review.stamp(NOW - timedelta(days=days_ago + 1))}", f"1m@{seen}"]
    return {f"{concept}:1": dict(base), f"{concept}:2": dict(base)}


def only(quiz, now=NOW):
    return learner_profile.mastery(quiz, now)[0]


def test_the_probability_decays_monotonically_toward_the_prior_and_never_rises():
    values = [mastery_model.decay(0.98, days, 3.0) for days in range(0, 120, 3)]
    assert values[0] == 0.98 and all(a >= b for a, b in zip(values, values[1:])) and values[-1] > mastery_model.PRIOR
    assert mastery_model.decay(0.2, 30, 3.0) == 0.2  # below the prior it is left alone
    assert mastery_model.retention(3.0, 3.0) == mastery_model.RETENTION_AT_INTERVAL and mastery_model.retention(0, 3.0) == 1.0
    assert mastery_model.retention(6.0, 3.0) < mastery_model.retention(3.0, 3.0) and mastery_model.retention(6.0, 12.0) > mastery_model.retention(6.0, 3.0)


def test_a_recent_demonstration_is_still_recognised_and_shows_the_small_decay():
    item = only(mastered_quiz(1))
    assert item["status"] == "mastered" and "refresh_reason" not in item
    assert item["p_mastery"] < item["p_at_last_answer"] and 0.9 < item["retention"] < 1.0 and item["days_since_evidence"] == 1.0


def test_an_overdue_concept_lapses_to_refresh_required_with_the_numbers_in_the_reason():
    item = only(mastered_quiz(30))
    assert item["status"] == "needs_refresh" and item["p_mastery"] < mastery_model.REFRESH_P <= item["p_at_last_answer"]
    assert "30 days ago" in item["refresh_reason"] and "heuristic" not in item["refresh_reason"] and "0.80" in item["refresh_reason"]
    assert item["mastery_low"] <= item["p_mastery"] <= item["mastery_high"]


def test_a_longer_review_interval_keeps_mastery_longer():
    assert only(mastered_quiz(20, interval_hours=72.0))["status"] == "needs_refresh"
    assert only(mastered_quiz(20, interval_hours=24.0 * 14))["status"] == "mastered"


def test_new_graded_evidence_restarts_the_clock_and_restores_mastery():
    lapsed = mastered_quiz(40)
    assert only(lapsed)["status"] == "needs_refresh"
    answered = {key: {**entry, "last_seen": spaced_review.stamp(NOW), "graded_attempts": 3, "graded_correct": 3, "graded_streak": 3, "attempts": 3, "knew": 3, "streak": 3} for key, entry in lapsed.items()}
    assert only(answered)["status"] == "mastered"


def test_a_missed_question_is_still_needs_practice_and_a_never_mastered_concept_is_untouched():
    assert only(mastered_quiz(1, last_outcome="missed"))["status"] == "needs_practice"
    thin = mastered_quiz(100)
    for entry in thin.values():
        entry.update(graded_attempts=1, graded_correct=1, graded_streak=1)
    item = only(thin)
    assert item["status"] == "progressing" and "refresh_reason" not in item


def test_graded_answer_times_not_last_seen_decide_how_long_ago_the_evidence_was():
    quiz = mastered_quiz(40, timed=True)
    for entry in quiz.values():
        entry["last_seen"] = spaced_review.stamp(NOW)  # a self-reported answer today is not graded evidence
    assert only(quiz)["status"] == "needs_refresh" and only(quiz)["days_since_evidence"] == 40.0


def test_profiles_without_answer_times_fall_back_to_last_seen():
    quiz = mastered_quiz(2)
    assert all("graded_history" not in entry for entry in quiz.values()) and only(quiz)["days_since_evidence"] == 2.0
    for entry in quiz.values():
        entry.pop("interval_hours")
    assert only(quiz)["status"] == "mastered"


def test_the_you_may_already_know_this_evidence_leaves_out_lapsed_mastery_and_answering_again_restores_it():
    fresh, lapsed = mastered_quiz(1, "Calculus"), mastered_quiz(60, "Probability")
    assert set(learner_profile.mastered({**fresh, **lapsed}, NOW)) == {"Calculus"}
    refreshed = {key: {**entry, "last_seen": spaced_review.stamp(NOW)} for key, entry in lapsed.items()}
    assert set(learner_profile.mastered({**fresh, **refreshed}, NOW)) == {"Calculus", "Probability"}


def test_the_curriculum_stops_hinting_at_lapsed_mastery():
    session = SimpleNamespace(session_id="a", paper_title="Paper", paper=SimpleNamespace(references=[]),
                              report={"paper": {"title": "Paper"}, "learning_plan": [{"concept": "Calculus", "estimated_hours": 2.0}], "missing_prerequisites": [{"concept": "Calculus", "importance": "essential"}], "study_progress": []})
    now = spaced_review.now()

    def hints(days_ago):
        quiz = mastered_quiz(0)
        for entry in quiz.values():
            entry["last_seen"] = spaced_review.stamp(now - timedelta(days=days_ago))
        return curriculum.build_curriculum([session], {"known": [], "studied": [], "quiz": quiz})["mastery_hints"]
    assert [h["concept"] for h in hints(1)] == ["Calculus"] and hints(60) == []
