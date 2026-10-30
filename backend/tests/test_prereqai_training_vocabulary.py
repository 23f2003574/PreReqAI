"""Overfitting, fine-tuning and Monte Carlo methods are detected with prerequisites and definitions."""
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


def test_terms_are_detected_by_name_and_alias():
    _, found = _detect("The model can overfit; we fine-tune it, and fine-tuning helps. Monte Carlo sampling and MCMC are used.")
    assert found == {"Overfitting": 1, "Fine-Tuning": 2, "Monte Carlo Method": 2}


def test_look_alike_words_and_references_are_not_concepts():
    assert _detect("A fine tuner adjusted the piano; the carlo family; a suit that does not fit.")[1] == {}
    assert _detect("Fine-tuning language models, a survey.", section="References")[1] == {}


def test_each_has_prerequisites_and_a_definition():
    paper, found = _detect("Overfitting, fine-tuning and Monte Carlo estimation.")
    assert len(found) == 3
    PrerequisiteDetector().detect(paper)
    assert {"Probability", "Neural Networks", "Calculus"} <= {item.concept for item in paper.prerequisites}
    ConceptExplanationEngine().explain(paper)
    assert {item.concept for item in paper.concept_explanations} == set(found)
