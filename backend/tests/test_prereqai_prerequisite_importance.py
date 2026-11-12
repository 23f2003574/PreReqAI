"""Prerequisite importance comes from how many detected concepts need it, not from a constant."""
import pytest

from backend.models import DetectedConcept, Paper
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector, rank_prerequisites

pytestmark = pytest.mark.prereqai


def _detect(**mentions):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.concepts = [DetectedConcept(name=n.replace("_", " "), domain="d", occurrences=c) for n, c in mentions.items()]
    return {p.concept: p for p in PrerequisiteDetector().detect(paper).prerequisites}


def test_confidence_is_the_measured_share_not_a_constant():
    found = _detect(Attention=4, Softmax=2, Dropout=1)  # Attention, Softmax, Dropout all have rules
    assert found["Probability"].confidence == 1.0  # all three need it
    assert found["Linear Algebra"].confidence == 0.33  # only Attention
    assert found["Neural Networks"].confidence == 0.33  # only Dropout


def test_essential_and_supporting_boundary():
    found = _detect(Attention=4, Softmax=2, Dropout=1, Backpropagation=1)  # 4 rule-bearing concepts
    assert found["Probability"].importance == "essential"      # 3 of 4
    assert found["Neural Networks"].importance == "essential"    # Dropout and Backpropagation: 2 of 4, exactly half
    assert found["Linear Algebra"].importance == "supporting"   # 1 of 4
    assert found["Calculus"].importance == "supporting"         # 1 of 4


def test_exactly_half_is_essential():
    found = _detect(Attention=1, Dropout=1)  # Probability needed by both; Linear Algebra and Neural Networks by one of two
    assert found["Linear Algebra"].importance == "essential" and found["Neural Networks"].importance == "essential"


def test_explanation_states_the_evidence():
    found = _detect(Attention=4, Softmax=2)
    assert "2 of the paper's 2 concepts" in found["Probability"].importance_reason and "6 mentions" in found["Probability"].importance_reason


def test_no_concepts_means_no_prerequisites():
    assert _detect() == {}


def test_ranking_orders_by_dependents_then_mentions_then_name():
    found = _detect(Attention=1, Softmax=1, Dropout=5)
    ranked = [p.concept for p in rank_prerequisites(found.values())]
    assert ranked[0] == "Probability"  # needed by all three
    assert ranked.index("Neural Networks") < ranked.index("Linear Algebra")  # one dependent each, but 5 mentions vs 1
