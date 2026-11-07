"""A study step that falls back to the default order and hours is logged; curated concepts plan silently and in the same order."""
import logging

from backend.models import MissingPrerequisite, Paper
from backend.prerequisites import PrerequisiteLearningPlanner


def _plan(*names):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.missing_prerequisites.extend(MissingPrerequisite(concept=n, satisfied=False, reason="Required") for n in names)
    return PrerequisiteLearningPlanner().generate(paper).learning_plan


def test_a_concept_without_a_curated_entry_is_reported(caplog):
    with caplog.at_level(logging.WARNING, logger="prereqai.planner"):
        plan = _plan("Probability", "Quantum Gravity")
    assert [s.concept for s in plan] == ["Probability", "Quantum Gravity"] and plan[1].estimated_hours == 5
    assert "Quantum Gravity" in caplog.text and "Probability" not in caplog.text


def test_curated_concepts_keep_their_order_and_hours_without_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="prereqai.planner"):
        plan = _plan("Calculus", "Linear Algebra")
    assert [(s.concept, s.estimated_hours) for s in plan] == [("Linear Algebra", 12), ("Calculus", 10)]
    assert caplog.text == ""
