import logging

import pytest

from backend.models import DetectedConcept, Paper
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai


def _detect(names):
    paper = Paper.__new__(Paper)
    paper.prerequisites = []
    paper.concepts = [DetectedConcept(name=n, domain="d", occurrences=1) for n in names]
    return PrerequisiteDetector().detect(paper)


def test_ordinary_detection_reports_no_gaps(caplog):
    with caplog.at_level(logging.WARNING, logger="prereqai.prerequisites"):
        paper = _detect(["Transformer"])
    assert paper.concepts_without_rules == []
    assert {p.concept for p in paper.prerequisites} >= {"Attention", "Neural Networks"}
    assert not caplog.records


def test_concept_without_a_rule_is_flagged_as_unsupported(caplog):
    with caplog.at_level(logging.WARNING, logger="prereqai.prerequisites"):
        paper = _detect(["Unruled Concept"])
    assert paper.concepts_without_rules == ["Unruled Concept"]
    assert paper.prerequisites == []
    assert "Unruled Concept" in caplog.text and "unknown, not absent" in caplog.text


def test_concept_with_an_explicit_empty_rule_is_not_flagged(monkeypatch):
    monkeypatch.setattr(PrerequisiteDetector, "PREREQUISITE_RULES", {**PrerequisiteDetector.PREREQUISITE_RULES, "Leaf": []})
    paper = _detect(["Leaf"])
    assert paper.concepts_without_rules == [] and paper.prerequisites == []


def test_mixed_input_flags_only_the_unruled_concept():
    paper = _detect(["Transformer", "Unruled Concept"])
    assert paper.concepts_without_rules == ["Unruled Concept"]
    assert paper.prerequisites
