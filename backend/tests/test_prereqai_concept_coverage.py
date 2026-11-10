import pytest

from backend.concepts.concept_coverage import concept_detection_coverage
from backend.concepts.concept_registry import ConceptRegistry
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph

pytestmark = pytest.mark.prereqai

TOTAL = len(ConceptRegistry().all())


def _detect(text):
    paper = Paper(source_path="x.pdf", metadata=None)
    paper.paragraphs = [Paragraph(paragraph_id=1, section_title="Introduction", content=text)] if text else []
    return RuleBasedConceptDetector().detect(paper)


def test_empty_input_has_zero_coverage():
    assert _detect("").concept_coverage == {"registered_concepts": TOTAL, "detected_concepts": 0, "detection_coverage_ratio": 0.0}


def test_zero_matches():
    paper = _detect("Nothing technical is said here.")
    assert paper.concept_coverage["detected_concepts"] == 0 and paper.concept_coverage["detection_coverage_ratio"] == 0.0


def test_partial_matches_match_detected_concepts():
    paper = _detect("Attention and softmax are used.")
    cov = paper.concept_coverage
    assert cov["detected_concepts"] == len(paper.concepts) >= 2
    assert cov["registered_concepts"] == TOTAL
    assert cov["detection_coverage_ratio"] == round(len(paper.concepts) / TOTAL, 4)
    assert 0 < cov["detection_coverage_ratio"] < 1


def test_complete_match():
    names = " ".join(c.name for c in ConceptRegistry().all())
    paper = _detect(names)
    assert paper.concept_coverage["detected_concepts"] == len(paper.concepts)
    assert concept_detection_coverage(5, 5)["detection_coverage_ratio"] == 1.0


def test_empty_registry_is_safe():
    assert concept_detection_coverage(0, 0) == {"registered_concepts": 0, "detected_concepts": 0, "detection_coverage_ratio": 0.0}
