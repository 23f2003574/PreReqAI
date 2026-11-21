"""The plan adapts to assessed answers: mastered steps are compressed, failed ones get more time and a remediation list, every change says why, overrides reverse it, and the calendar is re-checked."""
from datetime import date

import pytest

from backend import adaptive_plan

pytestmark = pytest.mark.prereqai
REPORT = {"learning_plan": [{"concept": "Probability", "estimated_hours": 10.0}, {"concept": "Calculus", "estimated_hours": 8.0}, {"concept": "Statistics", "estimated_hours": 6.0}],
          "missing_prerequisites": [{"concept": "Probability", "importance": "essential"}], "study_progress": []}


def answers(concept, outcomes, confidence="medium"):
    return [{"question_id": f"{concept}:{1 + i % 3}", "concept": concept, "outcome": "knew" if ok else "missed", "graded": True, "correct": ok, "confidence": confidence} for i, ok in enumerate(outcomes)]


def by(result, concept):
    return next(a for a in result["adjustments"] if a["concept"] == concept)


def test_demonstrated_mastery_compresses_a_step_and_failure_adds_time_and_remediation_with_reasons():
    attempts = answers("Probability", [True, True, True, True]) + answers("Calculus", [False, False, True])
    result = adaptive_plan.propose(REPORT, attempts)
    probability, calculus = by(result, "Probability"), by(result, "Calculus")
    assert probability["action"] == "compress" and probability["adjusted_hours"] == 3.0 and "4 of 4 assessed answers correct" in probability["reason"]
    assert calculus["action"] == "remediate" and calculus["adjusted_hours"] == 12.0 and "1 of 3" in calculus["reason"] and "missed are listed" in calculus["reason"]
    assert {item["question_id"] for item in result["remediation"]["Calculus"]} == {"Calculus:1", "Calculus:2"}
    assert all(item["question"] and item["answer"] for item in result["remediation"]["Calculus"])
    assert result["hours_before"] == 24.0 and result["hours_after"] == 3.0 + 12.0 + 6.0 and {p["concept"]: p["adapted"] for p in result["plan"]} == {"Probability": True, "Calculus": True, "Statistics": False}
    assert all(a["reason"] for a in result["adjustments"])  # every change is explained


def test_too_little_evidence_self_reported_answers_and_confident_misses_are_handled_conservatively():
    few = adaptive_plan.propose(REPORT, answers("Probability", [True, True]))
    assert by(few, "Probability")["action"] == "keep" and by(few, "Probability")["adjusted_hours"] == 10.0 and "not yet enough" in by(few, "Probability")["reason"]
    self_reported = [{"question_id": f"Probability:{n}", "concept": "Probability", "outcome": "knew", "revealed": True} for n in (1, 2, 3, 1)]
    assert adaptive_plan.propose(REPORT, self_reported)["adjustments"] == [] and adaptive_plan.propose(REPORT, self_reported)["hours_after"] == 24.0
    one_question = [{**a, "question_id": "Probability:1"} for a in answers("Probability", [True] * 4)]
    assert by(adaptive_plan.propose(REPORT, one_question), "Probability")["action"] == "keep"  # four answers to the same question are not breadth
    confident = answers("Statistics", [True, True, True, False, False], "high")
    assert by(adaptive_plan.propose(REPORT, confident), "Statistics")["action"] == "remediate" and "with high confidence" in by(adaptive_plan.propose(REPORT, confident), "Statistics")["reason"]


def test_an_override_restores_the_original_hours_and_can_be_reversed():
    attempts = answers("Probability", [True] * 4)
    rejected = adaptive_plan.propose(REPORT, attempts, {"Probability": "reject"})
    assert by(rejected, "Probability")["overridden"] is True and by(rejected, "Probability")["adjusted_hours"] == 10.0 and rejected["hours_after"] == 24.0
    restored = adaptive_plan.propose(REPORT, attempts, {})
    assert by(restored, "Probability")["overridden"] is False and by(restored, "Probability")["adjusted_hours"] == 3.0
    assert "Calculus" not in adaptive_plan.propose(REPORT, answers("Calculus", [False] * 3), {"Calculus": "reject"})["remediation"]


def test_studied_steps_are_left_alone_and_the_calendar_feasibility_is_checked_before_and_after():
    report = {**REPORT, "study_progress": [{"concept": "Statistics", "completed": True}]}
    calendar = {"today": date(2026, 11, 20), "deadline": date(2026, 11, 24), "daily_hours": 3.0}
    result = adaptive_plan.propose(report, answers("Probability", [True] * 4), calendar=calendar)
    assert [p["concept"] for p in result["plan"]] == ["Probability", "Calculus"] and result["feasibility"]["before"]["status"] == "infeasible" and result["feasibility"]["after"]["status"] == "achievable"
    assert result["feasibility"]["after"]["finish_date"] <= "2026-11-24"
