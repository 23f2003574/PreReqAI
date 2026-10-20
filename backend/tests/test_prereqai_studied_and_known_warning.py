"""--studied for a concept that --known dropped is explained, not reported as missing from the plan."""
from backend.platform import platform

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def test_studied_and_known_for_the_same_concept_gets_an_accurate_warning():
    outcome = platform.analyze(SAMPLE, known=["Calculus"], studied=["calculus"])
    assert outcome["warnings"] == ["--studied 'calculus' was ignored because you also said you already know it, so it is not in the study plan"]


def test_studied_name_outside_the_plan_keeps_the_not_in_plan_warning():
    outcome = platform.analyze(SAMPLE, known=["Calculus"], studied=["Not A Concept"])
    assert len(outcome["warnings"]) == 1 and "'Not A Concept' is not in this paper's study plan" in outcome["warnings"][0]


def test_studied_without_known_is_unaffected():
    outcome = platform.analyze(SAMPLE, studied=["Calculus"])
    assert outcome["warnings"] == []
