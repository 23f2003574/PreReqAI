"""Variational inference (ELBO) is detected with its prerequisites and a definition."""
import pytest

from backend.concepts.concept_explanation_engine import ConceptExplanationEngine
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai


def _detect(text):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="Body", content=text))
    RuleBasedConceptDetector().detect(paper)
    return paper, {concept.name: concept.occurrences for concept in paper.concepts}


def test_variational_inference_is_detected_by_name_and_alias():
    _, found = _detect("Variational inference maximises the ELBO, the evidence lower bound.")
    assert found == {"Variational Inference": 3}


def test_unrelated_use_of_variational_is_not_detected():
    _, found = _detect("The variational principle in physics and a variation of the method are unrelated.")
    assert "Variational Inference" not in found


def test_it_brings_its_prerequisites_and_has_a_definition():
    paper, found = _detect("We optimise the ELBO.")
    PrerequisiteDetector().detect(paper)
    assert {"Probability", "Information Theory", "Calculus"} <= {item.concept for item in paper.prerequisites}

    ConceptExplanationEngine().explain(paper)
    assert {item.concept for item in paper.concept_explanations} == set(found) == {"Variational Inference"}
