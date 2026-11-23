"""A mathematical study step that was planned for a day that has passed and is not done is reported as a missed session and moved, exactly like the plan's other steps."""
from datetime import date

import pytest

from backend import study_calendar

pytestmark = pytest.mark.prereqai
REPORT = {
    "learning_plan": [{"concept": "Calculus", "estimated_hours": 2.0}, {"concept": "Probability", "estimated_hours": 2.0}],
    "math_plan": [{"concept": "Math: Matrix calculus", "estimated_hours": 2.0}, {"concept": "Math: Entropy", "estimated_hours": 1.0, "skipped": True, "estimated_hours_original": 1.0}],
    "missing_prerequisites": [], "study_progress": [],
}


def test_planned_steps_follow_the_same_order_as_the_remaining_steps_and_leave_out_skipped_ones():
    planned = [(s.concept, s.estimated_hours) for s in study_calendar.planned_steps(REPORT)]
    assert planned == [("Calculus", 2.0), ("Probability", 2.0), ("Math: Matrix calculus", 2.0)]
    steps, _, _ = study_calendar.plan_inputs(REPORT)
    assert [s.concept for s in steps] == [c for c, _ in planned]


def test_an_unfinished_math_step_planned_for_a_passed_day_is_a_missed_session():
    steps, importance, studied = study_calendar.plan_inputs(REPORT)
    start, today = date(2026, 11, 20), date(2026, 11, 25)  # at 2 h a day the whole plan began on the 20th: Calculus, Probability and the math step took one day each
    built = study_calendar.build_calendar(steps, importance, 2.0, today, None, None, start, studied, study_calendar.planned_steps(REPORT))
    missed = {item["concept"]: item for item in built["missed_sessions"]}
    assert set(missed) == {"Calculus", "Probability", "Math: Matrix calculus"}
    assert missed["Math: Matrix calculus"]["moved_to"] is not None and missed["Math: Matrix calculus"]["date"] == "2026-11-22"


def test_a_finished_math_step_is_not_reported_as_missed():
    report = {**REPORT, "study_progress": [{"concept": "Calculus", "completed": True}, {"concept": "Probability", "completed": True}, {"concept": "Math: Matrix calculus", "completed": True}]}
    steps, importance, studied = study_calendar.plan_inputs(report)
    built = study_calendar.build_calendar(steps, importance, 2.0, date(2026, 11, 25), None, None, date(2026, 11, 20), studied, study_calendar.planned_steps(report))
    assert built["missed_sessions"] == []
