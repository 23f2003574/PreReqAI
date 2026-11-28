"""Sustained accuracy: a history with misses must show a Wilson lower bound of 0.70 before it can be rated mastered; a history with no miss is judged as before."""
import pytest

from backend import mastery_model as m
from backend.prereqai_eval import mastery_sim

pytestmark = pytest.mark.prereqai


def _run(outcomes):
    return m.estimate([(ok, "medium", f"q{i % 3}") for i, ok in enumerate(outcomes)])


def test_wilson_lower_bound_values():
    assert m.wilson_lower(0, 0) == 0.0 and abs(m.wilson_lower(11, 12) - 0.699) < 0.002 and m.wilson_lower(4, 4) < m.wilson_lower(8, 8)


def test_misses_need_a_sustained_accuracy_and_say_so():
    short = _run([True] * 7 + [False] + [True] * 2)  # 9 of 10: lower bound 0.65
    assert short["mastered"] is False and short["accuracy_low"] < 0.70 and "sustained" in short["reason"]
    assert _run([True] * 14 + [False] + [True] * 3)["mastered"] is True


def test_a_perfect_history_is_unchanged():
    assert _run([True] * 4)["mastered"] is True


def test_partial_knowers_are_declared_mastered_less_often_than_before_and_knowers_still_are():
    report = mastery_sim.evaluate()
    assert report["false_mastery_partial"] <= 0.16 < 0.335 and report["true_mastery_knower"] >= 0.95 and report["false_mastery_guesser"] <= 0.02 and report["false_mastery_crammer"] == 0.0
