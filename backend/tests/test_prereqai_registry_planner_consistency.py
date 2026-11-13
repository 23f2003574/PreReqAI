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
    # Information Theory, Optimization, Statistics and Stochastic Processes are base subjects that themselves have prerequisites, not registry concepts.
    assert set(RULES) - REGISTRY_NAMES <= {"Information Theory", "Optimization", "Statistics", "Stochastic Processes"}


def test_resources_belong_to_known_concepts():
    assert set(RESOURCES) <= RULE_TARGETS | REGISTRY_NAMES


def test_sequence_models_has_no_dangling_planner_entries():
    assert "Sequence Models" not in PLANNER.STUDY_ORDER
    assert "Sequence Models" not in PLANNER.STUDY_TIME


# --- every prerequisite subject carries all of its learning metadata ---
from backend.concepts.concept_explanation_engine import ConceptExplanationEngine
from backend.concepts.rule_based_concept_detector import _SUBJECT_TERMS
from backend.prerequisites.prerequisite_justification_engine import PrerequisiteJustificationEngine
from backend.tutor.rule_based_tutor import PREREQUISITE_DEFINITIONS

SUBJECTS = sorted(RULE_TARGETS)


@pytest.mark.parametrize("subject", SUBJECTS)
def test_every_prerequisite_subject_has_every_definition_and_learning_metadata(subject):
    assert subject in PLANNER.STUDY_ORDER and subject in PLANNER.STUDY_TIME, "planner position and study hours"
    assert subject in RESOURCES and RESOURCES[subject][3] == PLANNER.STUDY_TIME[subject], "a resource carrying the planner's hours"
    assert subject in PREREQUISITE_DEFINITIONS or subject in ConceptExplanationEngine.EXPLANATIONS, "a tutor definition"
    assert subject in PrerequisiteJustificationEngine.JUSTIFICATIONS, "a justification"
    assert subject in _SUBJECT_TERMS, "terms by which the paper's own mentions of it are counted"


@pytest.mark.parametrize("subject", SUBJECTS)
def test_a_subject_is_planned_after_every_subject_it_builds_on(subject):
    for needed in RULES.get(subject, ()):
        assert PLANNER.STUDY_ORDER[needed] < PLANNER.STUDY_ORDER[subject], f"{needed} must be studied before {subject}"


def test_the_new_subjects_attach_to_the_concepts_that_need_them():
    needing = lambda subject: {c for c, targets in RULES.items() if subject in targets}
    assert needing("Optimization") == {"Gradient Descent", "Adam Optimizer"}
    assert needing("Statistics") == {"Maximum Likelihood Estimation", "Overfitting", "Monte Carlo Method"}
    assert needing("Stochastic Processes") == {"Diffusion Model", "Forward Process", "Reverse Process", "Noise Schedule"}
    assert needing("Optimization") | needing("Statistics") | needing("Stochastic Processes") <= REGISTRY_NAMES
    assert RULES["Optimization"] == ["Calculus", "Linear Algebra"] and RULES["Statistics"] == ["Probability"]
    assert RULES["Stochastic Processes"] == ["Probability", "Calculus"]


def test_a_paper_on_gradient_descent_plans_optimization_after_calculus_and_before_neural_networks():
    from types import SimpleNamespace as N
    from backend.models import DetectedConcept, Paper

    paper = Paper(source_path="p.pdf", metadata=None)
    paper.concepts = [DetectedConcept(name="Gradient Descent", domain="deep_learning", occurrences=5)]
    PrerequisiteDetector().detect(paper)
    assert {p.concept for p in paper.prerequisites} == {"Calculus", "Linear Algebra", "Optimization"}
    from backend.prerequisites import MissingPrerequisiteAnalyzer

    MissingPrerequisiteAnalyzer().analyze(paper)
    PrerequisiteLearningPlanner().generate(paper)
    assert [step.concept for step in paper.learning_plan] == ["Linear Algebra", "Calculus", "Optimization"]
