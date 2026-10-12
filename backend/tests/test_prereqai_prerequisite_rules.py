"""Every concept PreReqAI can detect has prerequisite rules whose targets the plan, resources and justifications know."""
from backend.concepts.concept_registry import ConceptRegistry
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.prerequisites.missing_prerequisite_analyzer import MissingPrerequisiteAnalyzer
from backend.prerequisites.prerequisite_justification_engine import PrerequisiteJustificationEngine
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner
from backend.models import DetectedConcept, Paper

RULES = PrerequisiteDetector.PREREQUISITE_RULES


def test_every_registry_concept_has_at_least_one_prerequisite():
    missing = [c.name for c in ConceptRegistry().all() if not RULES.get(c.name)]
    assert not missing, missing


def test_every_rule_target_is_a_known_concept_or_foundation():
    foundations = {"Linear Algebra", "Probability", "Neural Networks", "Graphs", "Calculus"}
    known = {c.name for c in ConceptRegistry().all()} | foundations | {"Attention"}
    unknown = sorted({t for targets in RULES.values() for t in targets} - known)
    assert not unknown, unknown


def test_a_reinforcement_learning_paper_now_gets_a_complete_study_plan():
    paper = Paper(source_path="p.pdf", metadata=None, pages=[], sections=[])
    paper.concepts = [DetectedConcept(name="Q-Learning", domain="rl", occurrences=3),
                      DetectedConcept(name="Bellman Equation", domain="rl", occurrences=1)]
    PrerequisiteDetector().detect(paper)
    assert [p.concept for p in paper.prerequisites] == ["Markov Decision Process", "Probability"]
    assert all("Q-Learning" in p.reason or "Bellman" in p.reason for p in paper.prerequisites)

    PrerequisiteJustificationEngine().justify(paper)
    MissingPrerequisiteAnalyzer().analyze(paper)
    PrerequisiteLearningPlanner().generate(paper)
    assert {step.concept for step in paper.learning_plan} == {"Markov Decision Process", "Probability"}
    assert all(step.estimated_hours > 0 for step in paper.learning_plan)
