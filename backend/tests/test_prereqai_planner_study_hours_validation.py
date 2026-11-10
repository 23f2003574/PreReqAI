import logging
import math

import pytest

from backend.models import MissingPrerequisite, Paper
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner as Planner

pytestmark = pytest.mark.prereqai


def _plan(names):
    paper = Paper.__new__(Paper)
    paper.learning_plan = []
    paper.missing_prerequisites = [MissingPrerequisite(concept=n, satisfied=False, reason="r") for n in names]
    return Planner().generate(paper).learning_plan


def test_curated_hours_are_finite_positive_numbers():
    for concept, hours in Planner.STUDY_TIME.items():
        assert isinstance(hours, (int, float)) and not isinstance(hours, bool), concept
        assert math.isfinite(hours) and hours > 0, concept


def test_valid_hours_are_used_unchanged():
    assert [s.estimated_hours for s in _plan(["Linear Algebra", "Probability"])] == [12, 10]


def test_missing_entry_uses_logged_fallback(caplog):
    with caplog.at_level(logging.WARNING, logger="prereqai.planner"):
        plan = _plan(["Not A Concept"])
    assert plan[0].estimated_hours == Planner.FALLBACK_HOURS == 5
    assert "Not A Concept" in caplog.text


@pytest.mark.parametrize("bad", [0, -3, float("nan"), float("inf"), float("-inf"), "8", None, True])
def test_invalid_hours_fall_back_with_a_warning(monkeypatch, caplog, bad):
    monkeypatch.setattr(Planner, "STUDY_TIME", {**Planner.STUDY_TIME, "Linear Algebra": bad})
    with caplog.at_level(logging.WARNING, logger="prereqai.planner"):
        plan = _plan(["Linear Algebra"])
    assert plan[0].estimated_hours == 5
    assert "invalid study hours" in caplog.text
