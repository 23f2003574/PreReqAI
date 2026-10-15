"""'How long will this take?' with an empty plan must not claim the learner studied anything."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALL = "Linear Algebra,Probability,Calculus,Neural Networks"


def _ask(flag):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask",
                          "examples/prerequisites/sample-paper.pdf", "How long will this take?", flag, ALL],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return run.stdout


def test_everything_known_does_not_say_everything_was_studied():
    out = _ask("--known")
    assert "no prerequisites left to study" in out and "You have studied" not in out


def test_everything_studied_still_says_studied():
    assert "You have studied every planned prerequisite; no preparation time is left." in _ask("--studied")
