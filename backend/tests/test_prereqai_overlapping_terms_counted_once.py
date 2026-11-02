"""One mention is one occurrence even when the concept's name contains one of its own aliases (or the reverse)."""
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph

pytestmark = pytest.mark.prereqai


def _counts(text):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="Body", content=text))
    RuleBasedConceptDetector().detect(paper)
    return {concept.name: concept.occurrences for concept in paper.concepts}


@pytest.mark.parametrize("text, expected", [
    ("We use the Monte Carlo Method.", {"Monte Carlo Method": 1}),                      # alias "Monte Carlo" sits inside the name
    ("Monte Carlo Methods are used.", {"Monte Carlo Method": 1}),
    ("Maximum Likelihood Estimation (MLE) is used.", {"Maximum Likelihood Estimation": 2}),  # the name and the abbreviation
    ("stochastic gradient descent (SGD) is used.", {"Gradient Descent": 2}),            # alias contains the name
])
def test_a_single_mention_is_counted_once(text, expected):
    assert _counts(text) == expected


def test_separate_mentions_are_still_all_counted():
    assert _counts("Monte Carlo sampling and the Monte Carlo Method; MCMC too.") == {"Monte Carlo Method": 3}
