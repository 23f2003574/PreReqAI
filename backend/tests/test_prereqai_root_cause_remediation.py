"""Prerequisite-aware root-cause remediation: failing a concept reinstates a claimed-known prerequisite that no assessed answers back up, before the concept, unless it is demonstrated or the learner rejects it."""
import pytest

from backend import adaptive_plan
from backend.platform.prereqai_platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _fails(concept, n=3):
    return [{"graded": True, "concept": concept, "correct": False, "confidence": "high", "question_id": f"{concept}:{i}", "at": f"2026-11-2{i}T10:00:00Z"} for i in range(n)]


@pytest.fixture(scope="module")
def report():
    return PreReqAIPlatform().analyze(SAMPLE, known=["Calculus"])["report"]


def test_calculus_known_and_neural_networks_failed_reinstates_calculus_before_neural_networks(report):
    result = adaptive_plan.propose(report, _fails("Neural Networks"))
    step = next(a for a in result["adjustments"] if a["concept"] == "Calculus")
    assert step["action"] == "reinstate" and step["before"] == "Neural Networks" and "struggling with Neural Networks" in step["reason"]
    names = [p["concept"] for p in result["plan"]]
    assert names.index("Calculus") < names.index("Neural Networks")
    adapted = [s["concept"] for s in adaptive_plan.adapted_report(report, _fails("Neural Networks"))["learning_plan"]]
    assert adapted.index("Calculus") < adapted.index("Neural Networks")  # the calendar schedules this order


def test_a_prerequisite_with_graded_mastery_is_not_reinstated(report):
    good = [{"graded": True, "concept": "Calculus", "correct": True, "confidence": "medium", "question_id": f"Calculus:{i % 3}", "at": f"2026-11-{10 + i * 2}T10:00:00Z"} for i in range(8)]
    result = adaptive_plan.propose(report, [*good, *_fails("Neural Networks")])
    assert not any(a["concept"] == "Calculus" and a.get("before") for a in result["adjustments"])


def test_the_learner_can_reject_the_reinstatement(report):
    result = adaptive_plan.propose(report, _fails("Neural Networks"), overrides={"Calculus": "reject"})
    step = next(a for a in result["adjustments"] if a["concept"] == "Calculus")
    assert step["overridden"] and step["adjusted_hours"] == 0.0


def test_nothing_is_reinstated_without_a_failure_or_a_claim(report):
    assert not [a for a in adaptive_plan.propose(report, [])["adjustments"] if a.get("before")]
    unclaimed = PreReqAIPlatform().analyze(SAMPLE)["report"]
    assert not [a for a in adaptive_plan.propose(unclaimed, _fails("Neural Networks"))["adjustments"] if a.get("before")]
