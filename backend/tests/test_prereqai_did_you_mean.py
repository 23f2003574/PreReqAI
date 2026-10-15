"""A misspelt --known/--studied name is ignored with a warning that suggests the intended concept."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _warnings(*flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze",
                          "examples/prerequisites/sample-paper.pdf", *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return [line for line in run.stdout.splitlines() if "warning:" in line]


def test_typos_get_a_suggestion():
    out = _warnings("--studied", "Probabilty", "--known", "linear algebr")
    assert any("--studied 'Probabilty'" in w and "did you mean 'Probability'?" in w for w in out)
    assert any("--known 'linear algebr'" in w and "did you mean 'Linear Algebra'?" in w for w in out)


def test_unrelated_names_and_already_known_names_get_no_suggestion():
    out = _warnings("--studied", "Quantum Gravity", "--known", "Calculus", "--studied", "Calculus")
    assert len(out) == 2 and all("did you mean" not in w for w in out)
