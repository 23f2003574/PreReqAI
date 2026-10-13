"""The analyze summary shows which plan steps are studied and how much preparation is left."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _summary(*flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", SAMPLE, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0 and run.stderr == ""
    return run.stdout


def test_studied_steps_are_marked_and_remaining_hours_shown():
    out = _summary("--studied", "Probability", "--studied", "Calculus")
    assert "2. Probability (10h, studied) -> 3. Calculus (10h, studied) -> 4. Neural Networks (15h)" in out
    assert "preparation: ~47h over 16 days (27h left)" in out
    assert len(out.splitlines()) <= 5


def test_without_progress_the_summary_is_unchanged_and_a_finished_plan_shows_nothing_left():
    out = _summary()
    assert "studied" not in out and "left)" not in out
    assert "1. Linear Algebra (12h) -> 2. Probability (10h)" in out
    done = _summary("--studied", "Linear Algebra", "--studied", "Probability", "--studied", "Calculus",
                    "--studied", "Neural Networks")
    assert "Ready to Read" in done and "(0h left)" in done
