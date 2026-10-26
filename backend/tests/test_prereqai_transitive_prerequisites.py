"""A prerequisite the paper does not discuss still brings in what it needs, so the study plan is self-contained."""
from types import SimpleNamespace

from backend.prerequisites.prerequisite_detector import PrerequisiteDetector


def _detect(*names):
    paper = SimpleNamespace(concepts=[SimpleNamespace(name=n) for n in names], prerequisites=[])
    PrerequisiteDetector().detect(paper)
    return {p.concept: p.reason for p in paper.prerequisites}


def test_attention_needed_by_a_graph_attention_paper_brings_in_its_own_prerequisites():
    found = _detect("Graph Attention Network")
    assert set(found) == {"Graphs", "Attention", "Linear Algebra", "Probability"}
    assert found["Probability"] == "Required to understand Graph Attention Network"


def test_prerequisites_already_listed_keep_their_reasons_and_nothing_is_duplicated():
    found = _detect("Graph Attention Network", "Graph Convolution")
    assert found["Linear Algebra"] == "Required to understand Graph Convolution"
    assert len(found) == 4


def test_concepts_without_deeper_prerequisites_are_unchanged():
    assert set(_detect("Softmax")) == {"Probability"}
