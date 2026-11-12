"""The detector's alias spellings (SGD, backprop, RNN) mean the same concept to every tutor rule, not only to definitions."""
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


def test_quiz_on_an_alias_quizzes_that_concept_only():
    answer = _ask("Quiz me on SGD")
    assert answer.startswith("Gradient Descent Q1 (Easy)")
    assert "Transformer Q1" not in answer and "Attention Q1" not in answer
    assert _ask("Quiz me on SGD") == _ask("Quiz me on Gradient Descent")


def test_quiz_on_an_alias_quizzes_the_concept_it_names():
    assert _ask("Quiz me on RNN") == _ask("Quiz me on Recurrent Neural Network") and _ask("Quiz me on RNN").startswith("Recurrent Neural Network Q1 (")


def test_prerequisites_of_an_alias_are_those_of_the_concept():
    assert _ask("Which prerequisites does backprop need?") == _ask("Which prerequisites does Backpropagation need?")
    assert _ask("Which prerequisites does backprop need?") == "Backpropagation builds on Calculus, Neural Networks."
