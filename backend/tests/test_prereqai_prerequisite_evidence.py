"""Each prerequisite recommendation carries the evidence behind it, and says what that evidence does not show."""
from types import SimpleNamespace

import pytest

from backend.models import DetectedConcept, Paper, Paragraph
from backend.prerequisites.missing_prerequisite_analyzer import MissingPrerequisiteAnalyzer
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.reporting.learning_report_generator import KNOWN_REASON

pytestmark = pytest.mark.prereqai


def _paper(**counts):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.concepts = [DetectedConcept(name=name.replace("_", " "), domain="d", occurrences=count) for name, count in counts.items()]
    return paper


def _detect(**counts):
    paper = PrerequisiteDetector().detect(_paper(**counts))
    return paper, {p.concept: p for p in paper.prerequisites}


def test_strong_evidence_lists_each_dependent_concept_with_its_mentions_and_relation():
    _, found = _detect(Attention=6, Softmax=4)
    evidence = {e["concept"]: e for e in found["Probability"].evidence}
    assert evidence["Attention"] == {"concept": "Attention", "relation": "direct", "occurrences": 6}
    assert evidence["Softmax"]["occurrences"] == 4 and found["Probability"].dependent_mentions == 10
    assert "10 mentions" in found["Probability"].importance_reason


def test_a_prerequisite_reached_only_through_another_is_marked_indirect():
    _, found = _detect(Graph_Attention_Network=3)
    assert {e["relation"] for e in found["Probability"].evidence} == {"indirect"}  # via Attention, not stated by the GAT rule itself
    assert {e["relation"] for e in found["Graphs"].evidence} == {"direct"}


def test_weak_evidence_is_shown_as_it_is_not_inflated():
    _, found = _detect(Dropout=1)
    assert found["Neural Networks"].evidence == [{"concept": "Dropout", "relation": "direct", "occurrences": 1}]
    assert "1 mentions" in found["Neural Networks"].importance_reason


def test_missing_occurrence_data_is_unknown_not_zero():
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.concepts = [SimpleNamespace(name="Dropout", domain="d"), SimpleNamespace(name="Softmax", domain="d", occurrences=0)]
    found = {p.concept: p for p in PrerequisiteDetector().detect(paper).prerequisites}
    probability = found["Probability"]
    assert [e["occurrences"] for e in probability.evidence] == [None, None] and probability.dependent_mentions == 0
    assert "no mention count for 2" in probability.importance_reason


def test_the_note_says_association_not_establishment():
    _, found = _detect(Attention=6)
    note = found["Linear Algebra"].evidence_note
    assert "association" in note and "not something the paper states" in note and "only checked for mentions of Attention" in note
    assert "establishes" not in note and "proves" not in note


def test_unsupported_concepts_are_listed_and_have_no_invented_prerequisites():
    paper, found = _detect(Tokenization=2, Vision_Transformer=1)
    assert paper.concepts_without_rules == []  # both now have rules
    paper = PrerequisiteDetector().detect(_paper(Quantum_Gravity=3))
    assert paper.concepts_without_rules == ["Quantum Gravity"] and paper.prerequisites == []


def _statuses(**counts):
    paper = _paper(Transformer=2, **counts)
    paper.paragraphs = [Paragraph(1, "2 Method", " ".join(f"{c.name.lower()}." for c in paper.concepts for _ in range(c.occurrences)))]
    paper = PrerequisiteDetector().detect(paper)
    paper = MissingPrerequisiteAnalyzer().analyze(paper)
    return {m.concept: m for m in paper.missing_prerequisites}


def test_coverage_status_separates_covered_mentioned_and_not_mentioned():
    found = _statuses(Attention=5)
    assert (found["Attention"].status, found["Attention"].mentions, found["Attention"].satisfied) == ("covered", 5, True)
    found = _statuses(Attention=2)
    assert (found["Attention"].status, found["Attention"].satisfied) == ("mentioned_only", False)
    assert (found["Neural Networks"].status, found["Neural Networks"].mentions, found["Neural Networks"].satisfied) == ("not_mentioned", 0, False)


def test_a_detected_concept_without_a_count_is_unknown_and_stays_in_the_plan():
    paper = PrerequisiteDetector().detect(_paper(Transformer=2))
    paper.concepts.append(SimpleNamespace(name="Attention", domain="d"))
    item = {m.concept: m for m in MissingPrerequisiteAnalyzer().analyze(paper).missing_prerequisites}["Attention"]
    assert item.status == "unknown" and item.mentions is None and not item.satisfied and "cannot be judged" in item.reason


def test_the_known_reason_text_matches_the_platforms():
    import pathlib, re
    source = pathlib.Path(__file__).resolve().parents[1].joinpath("platform", "prereqai_platform.py").read_text(encoding="utf-8")
    assert re.search(r'^KNOWN_REASON = "([^"]+)"', source, re.M).group(1) == KNOWN_REASON
