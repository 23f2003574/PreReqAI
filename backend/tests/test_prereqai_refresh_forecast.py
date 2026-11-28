"""Forgetting-model-driven review forecast: the lapse date comes from the same decay model, lapsed concepts are due now, and /review/schedule and the calendar agree."""
from datetime import date, datetime, timedelta, timezone

import pytest

from backend import learner_profile, mastery_model, spaced_review, study_calendar

pytestmark = pytest.mark.prereqai
NOW = datetime(2026, 12, 20, 9, tzinfo=timezone.utc)


def _quiz(days_ago, interval_hours=72.0, concept="Calculus"):
    """A concept mastered by 14 correct answers on three questions, the last `days_ago` days before NOW."""
    last = NOW - timedelta(days=days_ago)
    quiz = {}
    for n, question in enumerate((f"{concept}:1", f"{concept}:2", f"{concept}:3")):
        times = [last - timedelta(days=2 * (13 - i)) for i in range(14) if i % 3 == n]
        quiz[question] = {"concept": concept, "attempts": len(times), "knew": len(times), "missed": 0, "streak": len(times), "last_outcome": "knew", "first_seen": spaced_review.stamp(times[0]),
                          "last_seen": spaced_review.stamp(times[-1]), "due": spaced_review.stamp(last), "interval_hours": interval_hours, "graded_attempts": len(times), "graded_correct": len(times),
                          "graded_streak": len(times), "high_confidence_right": 0, "high_confidence_wrong": 0, "graded_history": [f"1m@{spaced_review.stamp(t)}" for t in times]}
    return quiz


def test_days_until_lapse_inverts_the_decay_model():
    for p in (0.85, 0.95, 0.999):
        days = mastery_model.days_until_lapse(p, 3.0)
        assert abs(mastery_model.decay(p, days, 3.0) - mastery_model.REFRESH_P) < 1e-9
    assert mastery_model.days_until_lapse(0.7, 3.0) == 0.0


def test_the_forecast_date_is_when_the_model_lapses_and_a_lapsed_concept_is_due_now():
    fresh = learner_profile.mastery(_quiz(1), NOW)[0]
    assert fresh["status"] == "mastered" and fresh["refresh_due_at"]
    due = spaced_review.parse_time(fresh["refresh_due_at"])
    for delta, status in ((-1, "mastered"), (1, "needs_refresh")):  # a day before the forecast it is still mastered; a day after it has lapsed
        moment = due + timedelta(days=delta)
        assert learner_profile.mastery(_quiz(1), moment)[0]["status"] == status
    lapsed = learner_profile.refresh_forecast(_quiz(400), NOW)
    assert lapsed and lapsed[0]["lapsed"] and lapsed[0]["days_overdue"] > 0


def test_a_concept_never_rated_mastered_has_no_forecast():
    quiz = _quiz(1)
    for entry in quiz.values():
        entry.update(graded_attempts=1, graded_correct=1, graded_history=entry["graded_history"][-1:], attempts=1, knew=1, streak=1)
    assert learner_profile.refresh_forecast(quiz, NOW) == []


def test_the_profile_schedule_and_the_calendar_agree_on_the_refresh(tmp_path):
    path = tmp_path / "me.json"
    learner_profile.save(path, [], [], _quiz(1))
    schedule, problem = learner_profile.review_schedule(path, NOW.date(), 10, 365)
    assert not problem and schedule["refreshes"] and schedule["refreshes"][0]["concept"] == "Calculus"
    calendar = {"days": [{"date": NOW.date().isoformat(), "hours": 1.0}], "daily_hours": 2.0}
    study_calendar.add_reviews(calendar, schedule)
    refresh = calendar["refreshes"][0]
    assert refresh["due"] == schedule["refreshes"][0]["due"] and any(day["date"] == refresh["date"] and "Calculus" in day["concepts"] for day in calendar["reviews"])
    assert refresh["date"] == max(date.fromisoformat(refresh["due"][:10]), NOW.date()).isoformat()
