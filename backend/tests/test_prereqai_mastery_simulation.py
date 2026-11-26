"""The mastery estimate, measured on simulated learners: guessers, one-sitting crammers and partial knowers are not declared mastered, real knowers are, and the numbers are reproducible."""
import pytest

from backend.prereqai_eval import gate, mastery_sim

pytestmark = pytest.mark.prereqai


@pytest.fixture(scope="module")
def report():
    return mastery_sim.evaluate(learners=200, days=30)


def test_the_simulation_is_reproducible_and_reports_every_rate(report):
    assert report == mastery_sim.evaluate(learners=200, days=30)
    assert set(report) == {"learners", "days", "false_mastery_guesser", "false_mastery_partial", "false_mastery_crammer", "true_mastery_knower", "median_answers_to_mastery"}


def test_guessers_and_one_sitting_crammers_are_almost_never_declared_mastered_and_knowers_are(report):
    assert report["false_mastery_guesser"] <= 0.02
    assert report["false_mastery_crammer"] == 0.0  # the spacing rule: answers minutes apart are one sitting
    assert report["true_mastery_knower"] >= 0.95 and report["median_answers_to_mastery"] <= 6


def test_partial_knowers_are_the_known_weak_spot_and_are_reported_not_hidden(report):
    assert 0.0 < report["false_mastery_partial"] <= 0.40  # a learner right 60 percent of the time still reaches mastery in about a third of runs: the model is not calibrated (see mastery_model.py)


def test_the_gate_checks_the_simulation_with_floors_from_thresholds_json():
    checks = []
    gate.mastery_sim_checks(checks, gate.load_thresholds()["mastery_simulation"])
    assert {c["metric"] for c in checks} == {"no_false_mastery_guesser", "no_false_mastery_partial", "no_false_mastery_crammer", "true_mastery_knower"} and all(c["passed"] for c in checks)
    failing = []
    gate.mastery_sim_checks(failing, {"no_false_mastery_guesser": 1.01})
    assert any(not c["passed"] for c in failing)
