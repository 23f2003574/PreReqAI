"""The tutor understands the registry's alias spellings (SGD, backprop, RNN...) like the canonical concept names."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]


def _ask(question):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask",
                          "examples/prerequisites/sample-paper.pdf", question],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


@pytest.mark.parametrize("question, concept", [
    ("What is SGD?", "Gradient Descent"),
    ("what is stochastic gradient descent", "Gradient Descent"),
    ("What is backprop?", "Backpropagation"),
    ("What is an RNN?", "Recurrent Neural Network"),
])
def test_an_alias_is_answered_like_the_canonical_concept_name(question, concept):
    answer = _ask(question)
    assert answer.startswith(f"{concept}: "), answer
    assert "tutoring model has not yet been configured" not in answer


def test_an_alias_and_its_canonical_name_give_one_answer_not_two():
    assert _ask("Is SGD the same as gradient descent?").count("Gradient Descent:") == 1


def test_a_word_merely_containing_an_alias_is_not_a_match():
    assert "tutoring model has not yet been configured" in _ask("What is a grubby thing?")
