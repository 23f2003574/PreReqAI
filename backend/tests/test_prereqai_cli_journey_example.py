"""examples/prerequisites/cli_journey.py runs offline and shows a ticked plan carried into the next run."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_cli_journey_example_carries_a_ticked_concept_into_the_next_run():
    run = subprocess.run([sys.executable, "examples/prerequisites/cli_journey.py"], cwd=ROOT,
                         capture_output=True, text=True, timeout=180)

    assert run.returncode == 0, run.stderr
    out = run.stdout
    before, after = out.split("3. Re-run with --resume")
    assert "study plan: 1. Linear Algebra (12h) -> 2. Probability (10h) -> 3. Neural Networks (15h)" in before
    assert "(0/3 concepts ready)" in before and "  - Why: Probability is required" in before
    assert "1. Linear Algebra (12h, studied) -> 2. Probability (10h)" in after and "(1/3 concepts ready)" in after
    assert "(25h left)" in after
    assert "Study these in order before the paper: 2. Probability (~10 h); 3. Neural Networks (~15 h). Already studied: Linear Algebra." in after
