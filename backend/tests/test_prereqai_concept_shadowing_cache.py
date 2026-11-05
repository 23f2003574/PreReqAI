"""Which registry terms shadow which is a property of the registry, so detect() must compute it once, not once per paper."""
import pytest

from backend.concepts import rule_based_concept_detector as detector_module
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector

pytestmark = pytest.mark.prereqai


def _detect(text):
    paper = type("StubPaper", (), {})()
    paper.concepts = []
    paper.paragraphs = [type("P", (), {"content": text, "section_title": "Introduction"})()]
    return {c.name: c.occurrences for c in RuleBasedConceptDetector().detect(paper).concepts}


def test_a_longer_concept_is_not_also_counted_as_the_shorter_one():
    counts = _detect("Self-Attention helps. Attention alone appears once. Self-Attention again.")
    assert counts["Self-Attention"] == 2
    assert counts["Attention"] == 1


def test_shadowing_is_computed_once_across_papers():
    _detect("attention")
    before = detector_module._shadowing_terms.cache_info()
    _detect("self-attention and attention")
    _detect("gradient descent")
    after = detector_module._shadowing_terms.cache_info()
    assert after.misses == before.misses
    assert after.hits == before.hits + 2
