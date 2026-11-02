"""Alias rewriting keeps its output while the registry/alias map is built once, not for every question."""
import pytest

from backend.tutor import rule_based_tutor
from backend.tutor.rule_based_tutor import _alias_spellings, _canonical_question

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("question, expected", [
    ("Quiz me on SGD", "Quiz me on Gradient Descent"),
    ("Which prerequisites does backprop need?", "Which prerequisites does Backpropagation need?"),
    ("what is an rnn", "what is an Recurrent Neural Network"),
    ("Is stochastic gradient descent like SGD?", "Is Gradient Descent like Gradient Descent?"),
    ("What is softmax?", "What is softmax?"),
    ("Describe the paragraphs", "Describe the paragraphs"),
])
def test_alias_spellings_are_rewritten_to_the_concept_name(question, expected):
    assert _canonical_question(question) == expected


def test_the_registry_is_built_once_however_many_questions_are_asked(monkeypatch):
    _alias_spellings.cache_clear()
    built = []
    real = rule_based_tutor.ConceptRegistry

    def counting():
        built.append(1)
        return real()

    monkeypatch.setattr(rule_based_tutor, "ConceptRegistry", counting)
    for _ in range(50):
        _canonical_question("Quiz me on SGD")
    assert len(built) == 1
    _alias_spellings.cache_clear()
