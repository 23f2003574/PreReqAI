"""Consistency between the concept registry, prerequisite rules, planner tables and resources."""
import pytest

from backend.concepts.concept_registry import ConceptRegistry
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner
from backend.resources.learning_resource_recommender import LearningResourceRecommender

pytestmark = pytest.mark.prereqai

PLANNER = PrerequisiteLearningPlanner
RULES = PrerequisiteDetector.PREREQUISITE_RULES
RESOURCES = LearningResourceRecommender.RESOURCE_LIBRARY
REGISTRY_NAMES = {c.name for c in ConceptRegistry().get_concepts()} if hasattr(ConceptRegistry, "get_concepts") else {c.name for c in ConceptRegistry()._concepts}
RULE_TARGETS = {p for targets in RULES.values() for p in targets}
# Planner concepts that legitimately have no curated resource link (none is invented for them).
NO_RESOURCE_YET = {"Self-Attention", "Multi-Head Attention"}


def test_planner_tables_cover_the_same_concepts():
    assert set(PLANNER.STUDY_ORDER) == set(PLANNER.STUDY_TIME)


def test_every_planner_concept_is_reachable_as_a_prerequisite_or_registry_concept():
    # Base subjects (Linear Algebra, ...) are only ever prerequisites; others must be registry concepts.
    for name in PLANNER.STUDY_ORDER:
        assert name in RULE_TARGETS or name in REGISTRY_NAMES, f"{name} can never reach a plan"


def test_every_planner_concept_has_a_resource_unless_listed_as_exception():
    missing = sorted(set(PLANNER.STUDY_ORDER) - set(RESOURCES) - NO_RESOURCE_YET)
    assert not missing, f"no resource for: {missing}"
    assert not (NO_RESOURCE_YET & set(RESOURCES)), "stale exception: a resource now exists"


def test_rule_keys_are_registry_concepts():
    # Information Theory is a base subject that itself has a prerequisite (Probability), not a registry concept.
    assert set(RULES) - REGISTRY_NAMES <= {"Information Theory"}


def test_resources_belong_to_known_concepts():
    assert set(RESOURCES) <= RULE_TARGETS | REGISTRY_NAMES


def test_sequence_models_has_no_dangling_planner_entries():
    assert "Sequence Models" not in PLANNER.STUDY_ORDER
    assert "Sequence Models" not in PLANNER.STUDY_TIME
