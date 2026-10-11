"""Every concept PreReqAI can detect gets a definition and a difficulty in the report."""
from backend.concepts.concept_explanation_engine import ConceptExplanationEngine
from backend.concepts.concept_registry import ConceptRegistry
from backend.models import DetectedConcept, Paper

LEVELS = {"Beginner", "Intermediate", "Advanced"}


def _explained(*names):
    paper = Paper(source_path="p.pdf", metadata=None, pages=[], sections=[])
    paper.concepts = [DetectedConcept(name=name, domain="x", occurrences=1) for name in names]
    return {e.concept: e for e in ConceptExplanationEngine().explain(paper).concept_explanations}


def test_every_registry_concept_has_a_real_definition_and_a_known_difficulty():
    names = [c.name for c in ConceptRegistry().all()]
    explained = _explained(*names)
    assert set(explained) == set(names)
    for explanation in explained.values():
        assert len(explanation.definition.split()) >= 8 and explanation.definition.endswith(".")
        assert explanation.difficulty in LEVELS


def test_reinforcement_learning_and_graph_concepts_are_explained_and_unknown_ones_are_skipped():
    explained = _explained("Q-Learning", "Message Passing", "Quantum Gravity")
    assert set(explained) == {"Q-Learning", "Message Passing"}
    assert "state-action" in explained["Q-Learning"].definition and "neighbours" in explained["Message Passing"].definition
