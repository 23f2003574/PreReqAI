"""examples/prerequisites/study_journey.py runs offline and prints what the example README says it does."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_study_journey_example_runs_and_shows_the_documented_output():
    run = subprocess.run([sys.executable, "examples/prerequisites/study_journey.py"], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)

    assert run.returncode == 0, run.stderr
    out = run.stdout
    assert "Study plan: Linear Algebra (12h) -> Probability (10h) -> Neural Networks (15h)" in out
    assert "    Attention  [satisfied]\n      Linear Algebra\n      Probability\n    Neural Networks" in out
    assert "Studied Linear Algebra: 1/3 concepts ready" in out
    assert "Next to study: Probability, Neural Networks" in out
    assert "- [x] 1. Linear Algebra" in out and "- [ ] 2. Probability" in out
    assert "Tree after studying:\n  Transformer\n    Attention  [satisfied]\n      Linear Algebra  [studied]" in out
