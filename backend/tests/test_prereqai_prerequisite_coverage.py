"""A prerequisite is covered by the paper only when it is discussed (3+ mentions); a passing mention keeps it in the plan."""
import pytest

from backend.models import DetectedConcept, Paper, Prerequisite
from backend.prerequisites.missing_prerequisite_analyzer import COVERAGE_MIN_MENTIONS, MissingPrerequisiteAnalyzer

pytestmark = pytest.mark.prereqai


def _analyse(occurrences):
    paper = Paper.__new__(Paper)
    paper.concepts = [DetectedConcept(name="Attention", domain="transformers", occurrences=occurrences)] if occurrences else []
    paper.prerequisites = [Prerequisite(concept="Attention", reason="r", confidence=1.0)]
    paper.missing_prerequisites = []
    return MissingPrerequisiteAnalyzer().analyze(paper).missing_prerequisites[0]


@pytest.mark.parametrize("count", [1, COVERAGE_MIN_MENTIONS - 1])
def test_a_passing_mention_is_not_coverage(count):
    item = _analyse(count)
    assert not item.satisfied and "Mentioned" in item.reason and "external study" in item.reason


def test_substantive_treatment_is_coverage():
    item = _analyse(COVERAGE_MIN_MENTIONS)
    assert item.satisfied and item.reason.startswith("Covered within the paper")


def test_an_absent_concept_is_missing():
    item = _analyse(0)
    assert not item.satisfied and item.reason == "Requires external study"
