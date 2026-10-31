"""Embeddings are detected with prerequisites and a definition."""
import pytest

from backend.concepts.concept_explanation_engine import ConceptExplanationEngine
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai


def _detect(text, section="Body"):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title=section, content=text))
    RuleBasedConceptDetector().detect(paper)
    return paper, {concept.name: concept.occurrences for concept in paper.concepts}


def test_embedding_names_and_aliases_are_detected_with_prerequisites_and_definition():
    paper, found = _detect("Each token gets an embedding; word embeddings and word2vec vectors live in the embedding space.")
    assert found == {"Embedding": 4}
    PrerequisiteDetector().detect(paper)
    assert {"Linear Algebra", "Neural Networks"} <= {item.concept for item in paper.prerequisites}
    ConceptExplanationEngine().explain(paper)
    assert [item.concept for item in paper.concept_explanations] == ["Embedding"]


def test_look_alikes_and_references_are_not_embedding_concepts():
    assert _detect("The embedded system was embedded in a wall.")[1] == {}
    assert _detect("Word embeddings: a survey.", section="References")[1] == {}
