"""The adapted plan drives the schedule: calendar, .ics, plan text and curriculum use the hours the learner's assessed answers call for; rejecting restores the original; no assessed answers changes nothing."""
from datetime import date
from types import SimpleNamespace

import pytest

from backend import adaptive_plan, curriculum, study_calendar

pytestmark = pytest.mark.prereqai
TODAY = date(2026, 12, 1)


def report():
    return {"learning_plan": [{"step": 1, "concept": "Probability", "estimated_hours": 10.0}, {"step": 2, "concept": "Calculus", "estimated_hours": 8.0}],
            "missing_prerequisites": [{"concept": "Probability", "importance": "essential"}, {"concept": "Calculus", "importance": "essential"}],
            "paper": {"title": "A paper"}, "study_progress": []}


def attempts(concept, correct, n, confidence="medium"):
    return [{"question_id": f"{concept}:{i % 4 + 1}", "concept": concept, "outcome": "knew" if correct else "missed", "graded": True, "correct": correct, "confidence": confidence} for i in range(n)]


def session(attempts_=(), overrides=None):
    r = report()
    if overrides:
        r["adaptive_overrides"] = overrides
    return SimpleNamespace(report=r, quiz_attempts=list(attempts_), session_id="s1", paper_title="A paper")


def total(calendar):
    return round(sum(day["hours"] for day in calendar["days"]), 2)


def test_without_assessed_answers_the_report_and_calendar_are_unchanged():
    s = session()
    assert adaptive_plan.session_report(s) is s.report
    steps, importance, studied = study_calendar.plan_inputs(adaptive_plan.session_report(s))
    plain = study_calendar.build_calendar(steps, importance, 3.0, TODAY)
    assert "adapted_concepts" not in study_calendar.mark_adapted(plain, s.report) and all("adapted" not in i for d in plain["days"] for i in d["items"])


def test_calendar_hours_equal_the_adapted_plan_and_items_are_marked():
    s = session(attempts("Probability", True, 4) + attempts("Calculus", False, 2))
    proposal = adaptive_plan.propose(s.report, s.quiz_attempts, {})
    adapted = adaptive_plan.session_report(s)
    steps, importance, _ = study_calendar.plan_inputs(adapted)
    calendar = study_calendar.mark_adapted(study_calendar.build_calendar(steps, importance, 3.0, TODAY), adapted)
    assert total(calendar) == proposal["hours_after"] != proposal["hours_before"]
    assert calendar["adapted_concepts"] == ["Calculus", "Probability"] and all(i.get("adapted") for d in calendar["days"] for i in d["items"])
    assert "adapted to your assessed answers" in study_calendar.to_ics(calendar, title="t")


def test_a_rejected_override_restores_the_original_hours():
    s = session(attempts("Probability", True, 4), overrides={"Probability": "reject"})
    assert adaptive_plan.session_report(s) is s.report
    assert study_calendar.plan_inputs(adaptive_plan.session_report(s))[0][0].estimated_hours == 10.0


def test_the_curriculum_uses_adapted_hours_unless_asked_not_to():
    s = session(attempts("Probability", True, 4))
    adapted, original = curriculum.build_curriculum([s]), curriculum.build_curriculum([s], adapted=False)
    assert adapted["hours"]["combined"] < original["hours"]["combined"] == 18.0
