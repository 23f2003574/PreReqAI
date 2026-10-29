"""Variational autoencoders and GANs (with their plurals) are detected with prerequisites and definitions."""
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


def test_vaes_and_gans_are_detected_by_name_alias_and_plural():
    _, found = _detect("VAEs and the variational autoencoder differ from a GAN; generative adversarial networks and GANs are compared.")
    assert found == {"Variational Autoencoder": 2, "Generative Adversarial Network": 3}


def test_similar_words_are_not_detected():
    _, found = _detect("The vaeld sample, a gang of ganglia, and an adversarial attack on a classifier.")
    assert found == {}


def test_they_bring_prerequisites_and_have_a_definition():
    paper, found = _detect("We train a VAE and a GAN.")
    PrerequisiteDetector().detect(paper)
    assert {"Neural Networks", "Probability", "Information Theory", "Calculus"} <= {item.concept for item in paper.prerequisites}
    ConceptExplanationEngine().explain(paper)
    assert {item.concept for item in paper.concept_explanations} == set(found) == {"Variational Autoencoder", "Generative Adversarial Network"}
