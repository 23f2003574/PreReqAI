"""'Which prerequisites does Softmax need?' lists what that concept builds on, not only its definition."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ask(question, *flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask",
                          "examples/prerequisites/sample-paper.pdf", question, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout.splitlines()[0]


def test_a_concept_question_lists_its_prerequisites():
    assert _ask("Which prerequisites does Softmax need?") == "Softmax builds on Probability."


def test_studied_prerequisites_are_marked():
    assert _ask("What are the prerequisites of Backpropagation?", "--studied", "Calculus") == \
        "Backpropagation builds on Calculus (studied), Neural Networks."


def test_a_why_question_still_gets_the_definition():
    assert _ask("What is softmax?").startswith("Softmax: ")
