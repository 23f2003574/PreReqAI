"""Prerequisite importance comes from how many detected concepts need it, not from a constant."""
import pytest

from backend.models import DetectedConcept, Paper
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector, rank_prerequisites

pytestmark = pytest.mark.prereqai


def _detect(**mentions):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.concepts = [DetectedConcept(name=n.replace("_", " "), domain="d", occurrences=c) for n, c in mentions.items()]
    return {p.concept: p for p in PrerequisiteDetector().detect(paper).prerequisites}


def test_confidence_is_the_measured_share_not_a_constant():
    found = _detect(Attention=4, Softmax=2, Dropout=1)  # Attention, Softmax, Dropout all have rules
    assert found["Probability"].confidence == 1.0  # all three need it
    assert found["Linear Algebra"].confidence == 0.33  # only Attention
    assert found["Neural Networks"].confidence == 0.33  # only Dropout


def test_essential_and_supporting_boundary():
    found = _detect(Attention=4, Softmax=2, Dropout=1, Backpropagation=1)  # 4 rule-bearing concepts
    assert found["Probability"].importance == "essential"      # 3 of 4
    assert found["Neural Networks"].importance == "essential"    # Dropout and Backpropagation: 2 of 4, exactly half
    assert found["Linear Algebra"].importance == "supporting"   # 1 of 4
    assert found["Calculus"].importance == "supporting"         # 1 of 4


def test_exactly_half_is_essential():
    found = _detect(Attention=1, Dropout=1)  # Probability needed by both; Linear Algebra and Neural Networks by one of two
    assert found["Linear Algebra"].importance == "essential" and found["Neural Networks"].importance == "essential"


def test_explanation_states_the_evidence():
    found = _detect(Attention=4, Softmax=2)
    assert "2 of the paper's 2 concepts" in found["Probability"].importance_reason and "6 mentions" in found["Probability"].importance_reason


def test_no_concepts_means_no_prerequisites():
    assert _detect() == {}


def test_ranking_orders_by_dependents_then_mentions_then_name():
    found = _detect(Attention=1, Softmax=1, Dropout=5)
    ranked = [p.concept for p in rank_prerequisites(found.values())]
    assert ranked[0] == "Probability"  # needed by all three
    assert ranked.index("Neural Networks") < ranked.index("Linear Algebra")  # one dependent each, but 5 mentions vs 1


def test_report_lists_prerequisites_most_needed_first_and_keeps_the_plan_order():
    from backend.platform import platform

    report = platform.analyze("examples/prerequisites/sample-paper.pdf")["report"]
    listed = [p["concept"] for p in report["prerequisites"]]
    evidence = {p["concept"]: (len(p["evidence"]), p["importance"]) for p in report["prerequisites"]}
    assert [evidence[c][0] for c in listed] == sorted((evidence[c][0] for c in listed), reverse=True)
    assert [m["concept"] for m in report["missing_prerequisites"]] == [c for c in listed if c in {m["concept"] for m in report["missing_prerequisites"]}]
    assert {m["concept"]: m["importance"] for m in report["missing_prerequisites"]} == {c: evidence[c][1] for c in listed}
    assert all(label in ("essential", "supporting") for _, label in evidence.values())
    plan = [step["concept"] for step in report["learning_plan"]]
    from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner

    assert plan and plan == sorted(plan, key=lambda c: (PrerequisiteLearningPlanner.STUDY_ORDER.get(c, 999), c))


def test_ranking_does_not_depend_on_reason_text_and_ties_break_by_name():
    from types import SimpleNamespace as P

    items = [P(concept="B", reason="x", evidence=[1, 2], dependent_mentions=3), P(concept="A", reason="Required to understand X, Y, Z", evidence=[1], dependent_mentions=3),
             P(concept="C", reason="x", evidence=[1], dependent_mentions=3), P(concept="D", reason="x", evidence=[1], dependent_mentions=9)]
    assert [p.concept for p in rank_prerequisites(items)] == ["B", "D", "A", "C"]
    assert [p.concept for p in rank_prerequisites(reversed(items))] == ["B", "D", "A", "C"]
