import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph
from backend.models.paper import DocumentMetadata  # noqa: F401  (Paper requires metadata)

pytestmark = pytest.mark.prereqai


def _paper(text):
    paper = Paper(source_path="x.pdf", metadata=None)
    paper.paragraphs = [Paragraph(paragraph_id=1, section_title="Introduction", content=text)] if text else []
    return paper


def _detect(text):
    return RuleBasedConceptDetector().detect(_paper(text))


def test_unmatched_defined_term_is_reported_but_not_detected():
    paper = _detect("We use a Graph Isomorphism Network (GIN) layer. Attention helps.")
    assert paper.unrecognised_terms == ["Graph Isomorphism Network (GIN)"]
    assert [c.name for c in paper.concepts] == ["Attention"]


def test_recognised_concepts_are_not_reported():
    paper = _detect("A Recurrent Neural Network (RNN) and a Graph Neural Network (GNN) are used.")
    assert paper.unrecognised_terms == []
    assert {c.name for c in paper.concepts} >= {"Recurrent Neural Network", "Graph Neural Network"}


def test_ordinary_capitalised_text_is_not_reported():
    paper = _detect("The Quick Brown Fox met John Smith in New York. Figure Three (SOTA) is shown.")
    assert paper.unrecognised_terms == []


def test_candidates_are_deduplicated():
    paper = _detect("Graph Isomorphism Network (GIN) works. Graph Isomorphism Network (GIN) again.")
    assert paper.unrecognised_terms == ["Graph Isomorphism Network (GIN)"]


def test_empty_input():
    paper = _detect("")
    assert paper.unrecognised_terms == [] and paper.concepts == []
