import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph

pytestmark = pytest.mark.prereqai


def _found(text):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="Body", content=text))
    return {c.name: c.occurrences for c in RuleBasedConceptDetector().detect(paper).concepts}


def test_hyphenated_compound_modifiers_count_as_the_concept():
    found = _found("We use gradient-descent based training, a policy-gradient method and gradient descent itself.")
    assert found["Gradient Descent"] == 2
    assert found["Policy Gradient"] == 1


def test_hyphen_variant_does_not_match_inside_other_words():
    assert "Gradient Descent" not in _found("A gradient-descentless idea and subgradient-descent.")
