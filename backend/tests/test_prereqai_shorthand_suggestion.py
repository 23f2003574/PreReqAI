"""A shorthand concept name ("Linear", "Calc", "networks") gets a did-you-mean when exactly one planned concept fits."""
import pytest

from backend.platform.prereqai_platform import _did_you_mean

pytestmark = pytest.mark.prereqai

PLAN = ["Linear Algebra", "Probability", "Calculus", "Neural Networks"]


@pytest.mark.parametrize("typed, suggested", [
    ("Linear", "Linear Algebra"),      # one word of the name
    ("calc", "Calculus"),              # the start of the name
    ("networks", "Neural Networks"),
    ("Probabilty", "Probability"),     # typo suggestions are unchanged
])
def test_shorthand_names_get_a_suggestion(typed, suggested):
    assert _did_you_mean(typed, PLAN) == f" (did you mean {suggested!r}?)"


@pytest.mark.parametrize("typed, plan", [
    ("neural", ["Neural Networks", "Neural Architecture Search"]),   # ambiguous: no guess
    ("Quantum", PLAN),                                                # unrelated
    ("al", PLAN),                                                     # too short to mean anything
    ("Calculus", PLAN),                                               # spelled right: it is simply not in the plan
])
def test_ambiguous_unrelated_short_or_correct_names_get_no_suggestion(typed, plan):
    assert _did_you_mean(typed, plan) == ""
