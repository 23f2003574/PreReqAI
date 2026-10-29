"""A plural of an acronym alias ("GRUs", "DDPMs", "ELBOs") is a mention of its concept, as the plural of a name already is."""
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph

pytestmark = pytest.mark.prereqai


def _detect(text):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="Body", content=text))
    RuleBasedConceptDetector().detect(paper)
    return {concept.name: concept.occurrences for concept in paper.concepts}


def test_plural_acronym_aliases_are_counted():
    assert _detect("Both GRUs and LSTMs beat plain RNNs.") == {"Recurrent Neural Network": 3}
    assert _detect("Tight ELBOs help.") == {"Variational Inference": 1}


def test_singular_and_plural_are_counted_together_without_double_counting():
    assert _detect("A GRU, then GRUs, and an RNN, and RNNs.") == {"Recurrent Neural Network": 4}


def test_a_longer_word_that_merely_starts_with_an_alias_is_not_a_mention():
    assert _detect("The elbows ached; gruesome results; rnnoise.") == {}
