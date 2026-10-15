"""'Which course should I use for X?' is answered with the curated study link from the analysis."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ask(question, *flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask",
                          "examples/prerequisites/sample-paper.pdf", question, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout


def test_a_named_concept_gets_its_own_resource():
    out = _ask("Which course should I use to study calculus?")
    assert "Suggested resources: Calculus: MIT 18.01 Single Variable Calculus" in out and "https://ocw.mit.edu/" in out
    assert "Probability:" not in out.split("\n")[0]


def test_no_concept_named_lists_what_is_left_in_study_order_and_skips_studied():
    line = _ask("What resources do you recommend?", "--studied", "Linear Algebra").splitlines()[0]
    assert "Linear Algebra" not in line
    assert line.index("Probability") < line.index("Calculus") < line.index("Neural Networks")


def test_everything_studied_falls_back_to_the_existing_answer():
    out = _ask("What resources do you recommend?", "--studied", "Linear Algebra,Probability,Calculus,Neural Networks")
    assert "Suggested resources" not in out
