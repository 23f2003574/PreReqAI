"""'Quiz me on Softmax' returns that concept's practice questions with answers, through the CLI."""
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


def test_quiz_me_on_a_concept_returns_its_questions_and_answers():
    assert _ask("Quiz me on Softmax") == (
        "Softmax Q1 (Easy): Why does Softmax produce probabilities instead of raw scores? "
        "Answer: Because it normalizes values into a probability distribution.")


def test_quiz_with_no_concept_named_covers_the_paper_concepts_that_have_questions():
    answer = _ask("Quiz me")
    assert "Attention Q1" in answer and "Softmax Q1" in answer and "Transformer Q1" in answer


def test_quiz_on_a_concept_without_questions_says_so_and_a_normal_question_is_unchanged():
    assert _ask("Quiz me on Gradient Descent") == "There are no practice questions yet for Gradient Descent."
    assert _ask("What is softmax?").startswith("Softmax: ")
