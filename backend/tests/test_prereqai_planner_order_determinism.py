import math

import pytest

from backend.models import MissingPrerequisite, Paper
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner as Planner

pytestmark = pytest.mark.prereqai


def _plan(items):
    paper = Paper.__new__(Paper)
    paper.learning_plan = []
    paper.missing_prerequisites = [MissingPrerequisite(concept=n, satisfied=s, reason="r") for n, s in items]
    return Planner().generate(paper).learning_plan


def test_curated_orders_are_finite_numbers_ahead_of_the_fallback():
    for concept, order in Planner.STUDY_ORDER.items():
        assert isinstance(order, (int, float)) and not isinstance(order, bool), concept
        assert math.isfinite(order) and order < 999, concept


def test_uncurated_concepts_follow_curated_ones_in_name_order_whatever_the_input_order():
    first = _plan([(n, False) for n in ("Zeta", "Calculus", "Alpha")])
    second = _plan([(n, False) for n in ("Alpha", "Zeta", "Calculus")])
    assert [s.concept for s in first] == [s.concept for s in second] == ["Calculus", "Alpha", "Zeta"]


def test_a_concept_listed_twice_appears_once():
    plan = _plan([("Calculus", False), ("Calculus", False), ("Probability", False)])
    assert [(s.order, s.concept) for s in plan] == [(1, "Probability"), (2, "Calculus")]


def test_satisfied_prerequisites_are_left_out():
    assert [s.concept for s in _plan([("Probability", True), ("Calculus", False)])] == ["Calculus"]
