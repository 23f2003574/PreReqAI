"""Generated study plans are structurally sound: curated tables agree, hours are positive, prerequisites precede their dependants."""
import pytest

from backend.models import LearningStep, MissingPrerequisite, Paper
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner as Planner


def test_order_and_time_tables_cover_the_same_concepts_with_positive_values():
    assert set(Planner.STUDY_ORDER) == set(Planner.STUDY_TIME)
    assert all(hours > 0 for hours in Planner.STUDY_TIME.values())
    assert len(set(Planner.STUDY_ORDER.values())) == len(Planner.STUDY_ORDER)


def test_every_curated_prerequisite_is_ordered_before_the_concept_that_needs_it():
    for concept, targets in PrerequisiteDetector.PREREQUISITE_RULES.items():
        for target in targets:
            if concept in Planner.STUDY_ORDER and target in Planner.STUDY_ORDER:
                assert Planner.STUDY_ORDER[target] < Planner.STUDY_ORDER[concept], f"{target!r} must be studied before {concept!r}"


def test_a_generated_plan_is_numbered_from_one_with_named_steps_and_positive_hours():
    paper = Paper.__new__(Paper)
    paper.learning_plan = []
    names = ("Transformer", "Linear Algebra", "Attention")
    paper.missing_prerequisites = [MissingPrerequisite(concept=n, satisfied=False, reason="r") for n in names]
    plan = Planner().generate(paper).learning_plan
    assert [s.order for s in plan] == [1, 2, 3]
    assert [s.concept for s in plan] == ["Linear Algebra", "Attention", "Transformer"]
    assert all(isinstance(s, LearningStep) and s.concept and s.estimated_hours > 0 for s in plan)
