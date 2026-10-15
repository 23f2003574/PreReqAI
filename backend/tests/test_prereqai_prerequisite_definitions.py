"""A "What is X?" question about a prerequisite gets a definition, not only why it is needed."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _ask(question, *flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", SAMPLE, question, "--json", *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)["responses"][0]["answer"]


def test_prerequisite_question_gets_definition_then_reason():
    answer = _ask("What is probability?")
    assert answer.startswith("Probability: The mathematics of uncertainty")
    assert "Why it is needed here:" in answer


def test_paper_concept_definition_is_not_overridden_and_known_prerequisite_is_still_defined():
    assert _ask("What is attention?").startswith("Attention: A mechanism that allows a model to focus")
    known = _ask("What is calculus?", "--known", "Calculus")
    assert known.startswith("Calculus: The mathematics of change")
