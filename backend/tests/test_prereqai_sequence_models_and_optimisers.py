"""Recurrent networks (RNN, LSTM, GRU) and the Adam optimiser are detected with their prerequisites and definitions."""
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


def test_recurrent_networks_and_adam_are_detected_by_name_and_alias():
    _, found = _detect("An LSTM and a GRU are RNNs. We train with AdamW, the Adam optimizer, and long short-term memory units.")
    assert found == {"Recurrent Neural Network": 4, "Adam Optimizer": 2}


def test_a_person_called_adam_is_not_the_optimiser():
    _, found = _detect("Adam Smith and Adam Jones wrote the survey; we cite Adam et al. only for the bibliography of gradient descent.")
    assert "Adam Optimizer" not in found


def test_they_bring_their_prerequisites_and_have_a_definition():
    paper, found = _detect("We compare an RNN with the Adam optimizer.")
    PrerequisiteDetector().detect(paper)
    needed = {item.concept for item in paper.prerequisites}
    assert {"Neural Networks", "Calculus", "Probability"} <= needed

    ConceptExplanationEngine().explain(paper)
    assert {item.concept for item in paper.concept_explanations} == set(found) == {"Recurrent Neural Network", "Adam Optimizer"}
