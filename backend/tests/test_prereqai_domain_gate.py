import pytest

from backend.concepts.concept_registry import ConceptRegistry
from backend.prereqai_eval import gate, negative_controls

pytestmark = pytest.mark.prereqai


def test_non_ml_documents_produce_no_concept_and_no_prerequisite():
    report = negative_controls.evaluate()
    assert report["clean"] == 1.0, report["controls"]


def test_a_transformer_paper_still_detects_the_transformer():
    lines = ["Attention in Transformer Models", "1 Introduction", "The Transformer uses self-attention over tokens. A transformer model has an encoder and a decoder.", "Transformers are trained with gradient descent."]
    report = negative_controls.evaluate({"ml": lines})["controls"]["ml"]
    assert "Transformer" in report["concepts"] and "Regularization" not in report["concepts"]


def test_regularization_counts_in_technical_phrases():
    lines = ["Weight Decay", "1 Introduction", "We apply L2 regularization with weight decay to the model parameters to reduce overfitting of the training loss."]
    assert "Regularization" in negative_controls.evaluate({"ml": lines})["controls"]["ml"]["concepts"]


def test_the_two_new_ambiguous_concepts_are_declared():
    assert {c.name for c in ConceptRegistry().all() if c.ambiguous} >= {"Transformer", "Regularization"}


def test_the_gate_fails_when_a_control_leaks():
    checks = []
    leaky = {"x": ["Gradient Descent and Backpropagation", "1 Introduction", "Gradient descent trains a neural network by backpropagation of the cross-entropy loss."]}
    original = negative_controls.CONTROLS
    try:
        negative_controls.CONTROLS = leaky
        gate.negative_control_checks(checks, {"clean_share": 1.0})
    finally:
        negative_controls.CONTROLS = original
    assert checks[0]["passed"] is False
