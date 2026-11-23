"""Mastery that has gone unreviewed far past its due date is no longer offered as "you may already know this": it needs a refresh, with the reason, until the learner answers again."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend import curriculum, learner_profile, spaced_review

pytestmark = pytest.mark.prereqai
NOW = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc)


def mastered_quiz(due_days_from_now, concept="Calculus", last_outcome="knew"):
    """Two questions answered correctly four times in all (assessed), each due `due_days_from_now` days from NOW."""
    stamp = spaced_review.stamp(NOW + timedelta(days=due_days_from_now))
    base = {"concept": concept, "attempts": 2, "knew": 2, "missed": 0, "streak": 2, "last_outcome": last_outcome, "first_seen": "2026-10-01T00:00:00Z", "last_seen": "2026-10-02T00:00:00Z",
            "interval_hours": 72.0, "due": stamp, "graded_attempts": 2, "graded_correct": 2, "graded_streak": 2}
    return {f"{concept}:1": dict(base), f"{concept}:2": dict(base)}


def only(quiz, now=NOW):
    return learner_profile.mastery(quiz, now)[0]


def test_mastery_holds_while_reviews_are_on_time_or_within_the_grace_period():
    for days in (30, 0, -1, -learner_profile.OVERDUE_GRACE_DAYS):
        item = only(mastered_quiz(days))
        assert item["status"] == "mastered" and "refresh_reason" not in item, days


def test_mastery_needs_a_refresh_once_a_review_is_overdue_beyond_the_grace_period_and_says_why():
    item = only(mastered_quiz(-(learner_profile.OVERDUE_GRACE_DAYS + 1)))
    assert item["status"] == "needs_refresh" and item["p_mastery"] >= 0.95  # the estimate is unchanged: nothing is claimed about how much was forgotten
    assert "2 reviews overdue by more than 14 days" in item["refresh_reason"] and "2026-12-05" in item["refresh_reason"]


def test_one_overdue_question_is_enough_and_a_missed_question_is_still_needs_practice():
    quiz = mastered_quiz(30)
    quiz["Calculus:2"]["due"] = spaced_review.stamp(NOW - timedelta(days=40))
    assert only(quiz)["status"] == "needs_refresh" and "1 review overdue" in only(quiz)["refresh_reason"]
    missed = mastered_quiz(-40, last_outcome="missed")
    assert only(missed)["status"] == "needs_practice" and "refresh_reason" not in only(missed)


def test_a_concept_that_was_never_mastered_is_not_touched_by_an_overdue_review():
    quiz = mastered_quiz(-100)
    for entry in quiz.values():
        entry.update(graded_attempts=1, graded_correct=1, graded_streak=1)
    assert only(quiz)["status"] == "progressing"


def test_the_you_may_already_know_this_evidence_leaves_out_lapsed_mastery_and_answering_again_restores_it():
    fresh, lapsed = mastered_quiz(10, "Calculus"), mastered_quiz(-60, "Probability")
    assert set(learner_profile.mastered({**fresh, **lapsed}, NOW)) == {"Calculus"}
    refreshed = {key: {**entry, "due": spaced_review.stamp(NOW + timedelta(days=20))} for key, entry in lapsed.items()}
    assert set(learner_profile.mastered({**fresh, **refreshed}, NOW)) == {"Calculus", "Probability"}


def test_the_curriculum_stops_hinting_at_lapsed_mastery():
    session = SimpleNamespace(session_id="a", paper_title="Paper", paper=SimpleNamespace(references=[]),
                              report={"paper": {"title": "Paper"}, "learning_plan": [{"concept": "Calculus", "estimated_hours": 2.0}], "missing_prerequisites": [{"concept": "Calculus", "importance": "essential"}], "study_progress": []})
    now = spaced_review.now()
    def hints(days):
        quiz = mastered_quiz(0)
        for entry in quiz.values():
            entry["due"] = spaced_review.stamp(now + timedelta(days=days))
        return curriculum.build_curriculum([session], {"known": [], "studied": [], "quiz": quiz})["mastery_hints"]
    assert [h["concept"] for h in hints(30)] == ["Calculus"] and hints(-60) == []
