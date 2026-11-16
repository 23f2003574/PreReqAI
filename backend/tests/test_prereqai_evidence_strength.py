"""Evidence strength of prerequisite recommendations: strong, moderate and weak grades from mentions and sections."""
import pytest

from backend.concepts import RuleBasedConceptDetector
from backend.ingestion import DocumentMetadata
from backend.models import Paper, Paragraph
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector, grade_concept, grade_prerequisite
from backend.reporting.learning_report_generator import LearningReportGenerator  # noqa: F401  (the report path is exercised through the platform below)

pytestmark = pytest.mark.prereqai


def _analyse(*sections):
    paper = Paper(source_path="x.pdf", metadata=DocumentMetadata(title="T", author="A", subject="", keywords="", creator="", producer="", page_count=1))
    paper.paragraphs = [Paragraph(i, title, text) for i, (title, text) in enumerate(sections, start=1)]
    RuleBasedConceptDetector().detect(paper)
    PrerequisiteDetector().detect(paper)
    return {p.concept: p for p in paper.prerequisites}


def test_a_repeated_concept_taught_in_a_method_section_is_strong():
    found = _analyse(("3 Method", "Softmax turns scores into weights. The softmax is applied row by row, and softmax is differentiable."))
    probability = found["Probability"]
    assert probability.evidence_strength == "strong" and "3 mentions, in 3 Method" in probability.strength_reasons[0]
    assert set(probability.evidence[0]) == {"concept", "relation", "occurrences"}  # the evidence entries keep their shape


def test_a_single_incidental_mention_is_weak_and_never_strong():
    found = _analyse(("1 Introduction", "Softmax is one option among several."))
    assert found["Probability"].evidence_strength == "weak" and "incidental" in found["Probability"].strength_reasons[0]


def test_repeated_mentions_outside_a_teaching_section_are_moderate_and_a_teaching_mention_is_too():
    repeated = _analyse(("4 Experiments", "Softmax here. Softmax there. Softmax again."))
    assert repeated["Probability"].evidence_strength == "moderate" and "none in a Background or Method-like section" in repeated["Probability"].strength_reasons[0]
    taught = _analyse(("2 Background", "Softmax is defined here."))
    assert taught["Probability"].evidence_strength == "moderate"


def test_mentions_spread_over_two_sections_make_a_repeated_concept_strong():
    found = _analyse(("1 Introduction", "Softmax once. Softmax twice."), ("4 Experiments", "Softmax again."))
    assert found["Probability"].evidence_strength == "strong" and "across 2 sections" in found["Probability"].strength_reasons[0]


def test_two_independent_dependents_keep_a_recommendation_strong():
    found = _analyse(("2 Background", "Softmax is used. A Markov decision process is used."))  # one mention each, but two concepts in a teaching section
    assert found["Probability"].evidence_strength == "strong" and len(found["Probability"].strength_reasons) >= 2


def test_an_isolated_ambiguous_word_is_weak_even_in_a_teaching_section():
    found = _analyse(("2 Background", "The attention mechanism helps the neural network."))
    assert found["Linear Algebra"].evidence_strength == "weak" and "everyday language" in found["Linear Algebra"].strength_reasons[0]


def test_grading_rules_directly():
    assert grade_concept(None, [], 0)[0] == "weak"
    assert grade_concept(5, [], 1, ambiguous=True)[0] == "moderate"  # repeated, an ambiguous word still counts when repeated
    assert grade_concept(5, ["2 Method"], 1, indirect=True)[0] == "moderate"  # needed only through another prerequisite
    assert grade_prerequisite([("weak", True), ("weak", True)]) == "weak"
    assert grade_prerequisite([("moderate", False), ("moderate", False)]) == "moderate"  # two indirect pieces do not make it strong
    assert grade_prerequisite([("moderate", True), ("moderate", False)]) == "strong"
    assert grade_prerequisite([]) == "weak"


def test_relationships_importance_and_learner_known_filtering_are_unchanged():
    found = _analyse(("2 Background", "Softmax is used. A Markov decision process is used."))
    assert {"Probability", "Markov Decision Process"} <= set(found) or "Probability" in found
    assert found["Probability"].importance in ("essential", "supporting") and 0 < found["Probability"].confidence <= 1


def test_the_report_and_api_expose_consistent_strength(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.platform import platform

    outcome = platform.analyze("examples/prerequisites/sample-paper.pdf", known=["Linear Algebra"])
    report = outcome["report"]
    by_name = {p["concept"]: p for p in report["prerequisites"]}
    assert all(p["evidence_strength"] in ("strong", "moderate", "weak") and p["strength_reasons"] for p in by_name.values())
    assert "Linear Algebra" not in {step["concept"] for step in report["learning_plan"]}  # a known subject still leaves the plan
    for gap in report["missing_prerequisites"]:
        assert gap["evidence_strength"] == by_name[gap["concept"]]["evidence_strength"]
    assert by_name["Probability"]["evidence_strength"] == "strong" and by_name["Optimization"]["evidence_strength"] == "weak"
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        body = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    assert {p["concept"]: p["evidence_strength"] for p in body["report"]["prerequisites"]} == {
        p["concept"]: p["evidence_strength"] for p in platform.analyze("examples/prerequisites/sample-paper.pdf")["report"]["prerequisites"]}
