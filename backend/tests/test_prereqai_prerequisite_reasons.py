"""A prerequisite needed by several concepts says so, instead of naming only the first one."""
from backend.platform import platform

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def test_shared_prerequisite_reason_names_every_concept_that_needs_it():
    report = platform.analyze(SAMPLE)["report"]
    reasons = {p["concept"]: p["reason"] for p in report["prerequisites"]}

    assert reasons["Linear Algebra"] == "Required to understand Attention, Gradient Descent"
    assert reasons["Probability"] == "Required to understand Attention, Softmax"
    assert reasons["Calculus"] == "Required to understand Gradient Descent, Backpropagation, Recurrent Neural Network"
    assert [p["concept"] for p in report["prerequisites"]].count("Linear Algebra") == 1
