"""Document-level domain gate: documents from other fields yield no machine-learning concept or prerequisite; machine-learning text is still read."""
import pytest

from backend.prereqai_eval import negative_controls as nc

pytestmark = pytest.mark.prereqai


def test_every_negative_control_is_clean():
    report = nc.evaluate()
    assert len(report["controls"]) >= 12
    leaked = {k: v for k, v in report["controls"].items() if v["concepts"] or v["prerequisites"]}
    assert report["clean"] >= 0.95, leaked


def test_machine_learning_positive_control_keeps_its_concepts():
    report = nc.evaluate(nc.POSITIVE_CONTROLS)
    row = report["controls"]["ml-short"]
    assert {"Fine-Tuning", "Backpropagation"} <= set(row["concepts"]) and row["prerequisites"]


def test_detector_reports_abstention():
    from backend.concepts.rule_based_concept_detector import ml_cues

    assert len(ml_cues("the dopamine gradient and neural networks in mice")) < 2
    assert len(ml_cues("a neural network trained by gradient descent with backpropagation")) >= 3
