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


def test_progress_question_reports_studied_count_and_names():
    assert _ask("How much have I completed?", "--studied", "Probability,Calculus") == \
        "You have studied 2 of 4 planned prerequisites (50%). Studied: Probability, Calculus."
    assert _ask("What is my progress?") == "You have studied 0 of 4 planned prerequisites (0%)."


def test_concepts_question_lists_detected_concepts_most_mentioned_first():
    assert _ask("Which concepts does this paper cover?") == (
        "The paper discusses these concepts, most mentioned first: Attention (4x), Softmax (3x), "
        "Gradient Descent (2x), Transformer (1x), Backpropagation (1x).")
