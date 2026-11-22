"""Mathematical gaps become study steps with hours and diagnostics, are scheduled and adapted with the plan, and demonstrated mastery makes a step skippable."""
from datetime import date

import pytest

from backend import adaptive_plan, math_plan, study_calendar
from backend.models import Equation
from backend.parsing import math_subtopics
from backend.tutor import diagnostic
from backend.tutor.math_quiz import MATH_QUIZ, MATH_SUBJECT
from backend.tutor.quiz_bank import QUIZ_EXPLANATIONS
from backend.tutor.quiz_session import ASKABLE

pytestmark = pytest.mark.prereqai
SOFTMAX_EQUATION = "Attention(Q, K, V) = softmax(QK^T / √d_k) V"
RESOURCES = {"Probability": ("Course", "Web", "https://example.org/p", 20.0), "Linear Algebra": ("Course", "Web", "https://example.org/la", 30.0)}


def subtopics(*expressions):
    equations = [Equation(n, text, "3 Method", 4, str(n), "") for n, text in enumerate(expressions, start=1)]
    return math_subtopics.analyse(equations, resource_for=lambda subject: RESOURCES.get(subject))


def report():
    found = math_plan.build(subtopics(SOFTMAX_EQUATION))
    return {"learning_plan": [{"step": 1, "concept": "Calculus", "estimated_hours": 10.0}], "missing_prerequisites": [{"concept": "Calculus", "importance": "essential"}], "study_progress": [], "math_plan": found}


def test_a_softmax_equation_gives_an_actionable_math_step_with_resource_hours_and_a_diagnostic():
    steps = {s["subtopic"]: s for s in math_plan.build(subtopics(SOFTMAX_EQUATION))}
    softmax = steps["Softmax and normalised exponentials"]
    assert softmax["concept"] == "Math: Softmax and normalised exponentials" and softmax["estimated_hours"] == 3.0 and softmax["resource"]["url"] == "https://example.org/p" and softmax["diagnostic"] is True
    assert steps["Matrix multiplication and transpose"]["estimated_hours"] == 4.5 and all(s["estimated_hours"] >= math_plan.MIN_HOURS for s in steps.values())
    assert math_plan.build([{"subtopic": "Integration", "subject": "Calculus", "why": "w", "equation_count": 1, "resource": None}])[0]["estimated_hours"] == math_plan.MIN_HOURS


def test_every_math_subtopic_rule_has_questions_with_explanations():
    assert {"Math: " + topic for topic, _, _, _ in math_subtopics.RULES} == set(MATH_QUIZ) == set(MATH_SUBJECT)
    for name, items in MATH_QUIZ.items():
        assert len(items) == 2 and name in ASKABLE
        for item in items:
            assert item["question"].endswith("?") and len(item["answer"]) > 30 and QUIZ_EXPLANATIONS[(name, item["question"])]


def test_the_plan_calendar_and_assessment_include_the_math_steps():
    r = report()
    steps, _, _ = study_calendar.plan_inputs(r)
    assert [s.concept for s in steps][0] == "Calculus" and any(s.concept.startswith("Math: Softmax") for s in steps)
    calendar = study_calendar.build_calendar(steps, {}, 24.0, date(2026, 12, 1))
    assert {i["concept"] for d in calendar["days"] for i in d["items"]} >= {s.concept for s in steps}


def graded(concept, flags):
    return [{"question_id": f"{concept}:{1 + n % 2}", "concept": concept, "outcome": "knew" if f else "missed", "graded": True, "correct": f, "confidence": "medium"} for n, f in enumerate(flags)]


def test_demonstrated_mastery_makes_a_math_step_skippable_and_a_rejection_restores_it():
    name = "Math: Softmax and normalised exponentials"
    r, attempts = report(), graded(name, [True] * 4)
    proposal = adaptive_plan.propose(r, attempts)
    skip = next(a for a in proposal["adjustments"] if a["concept"] == name)
    assert skip["action"] == "skip" and skip["adjusted_hours"] == 0.0 and skip["can_override"] and "skipped" in skip["reason"] and proposal["hours_after"] == proposal["hours_before"] - skip["original_hours"]
    adapted = adaptive_plan.adapted_report(r, attempts)
    assert next(s for s in adapted["math_plan"] if s["concept"] == name)["skipped"] is True and name not in [s.concept for s in study_calendar.plan_inputs(adapted)[0]]
    rejected = adaptive_plan.adapted_report(r, attempts, {name: "reject"})
    assert name in [s.concept for s in study_calendar.plan_inputs(rejected)[0]]


def test_a_non_math_step_is_never_skipped_and_a_weak_math_step_gets_more_time():
    r = report()
    assert next(a for a in adaptive_plan.propose(r, graded("Calculus", [True] * 4))["adjustments"] if a["concept"] == "Calculus")["action"] == "compress"
    name = "Math: Softmax and normalised exponentials"
    weak = next(a for a in adaptive_plan.propose(r, graded(name, [False, False, True]))["adjustments"] if a["concept"] == name)
    assert weak["action"] == "remediate" and weak["adjusted_hours"] > weak["original_hours"]


def test_math_questions_are_served_with_related_distractors():
    name = "Math: Gaussian distribution"
    options = diagnostic.options_for(name + ":1")
    assert len(options) == 4 and not diagnostic.weak_distractors(name + ":1")


def test_the_page_lists_the_math_steps_and_offers_their_questions():
    from pathlib import Path

    page = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    assert "report.math_plan" in page and "study steps in your calendar" in page and "quizConcept" in page
