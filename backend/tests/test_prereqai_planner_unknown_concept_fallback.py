"""A concept without a curated entry gets the fallback position (last), 5 hours and a logged warning; curated concepts are unchanged."""
import logging

from backend.models import MissingPrerequisite, Paper
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner as Planner


def _plan(names):
    paper = Paper.__new__(Paper)
    paper.learning_plan = []
    paper.missing_prerequisites = [MissingPrerequisite(concept=n, satisfied=False, reason="r") for n in names]
    return Planner().generate(paper).learning_plan


def test_an_unknown_concept_sorts_last_with_five_hours_and_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="prereqai.planner"):
        plan = _plan(["Zebra Theory", "Transformer", "Linear Algebra"])
    assert [s.concept for s in plan] == ["Linear Algebra", "Transformer", "Zebra Theory"]
    assert [s.order for s in plan] == [1, 2, 3]
    assert plan[-1].estimated_hours == 5
    assert plan[0].estimated_hours == Planner.STUDY_TIME["Linear Algebra"]
    assert any("Zebra Theory" in r.getMessage() and "fallback" in r.getMessage() for r in caplog.records)


def test_curated_concepts_produce_no_fallback_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="prereqai.planner"):
        _plan(["Linear Algebra", "Probability"])
    assert not caplog.records
