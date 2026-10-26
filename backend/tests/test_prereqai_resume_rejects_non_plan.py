"""--resume with a file that is not a saved plan is refused, not silently treated as 'nothing studied yet'."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER = "examples/prerequisites/sample-paper.pdf"


def _run(*args):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_resume_from_a_file_that_is_not_a_plan_fails_with_a_usage_error(tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text("- [x] 1. Probability (~10h)\n", encoding="utf-8")  # looks ticked but is not a saved plan
    for command in (("analyze", PAPER), ("ask", PAPER, "What should I learn first?")):
        run = _run(*command, "--resume", str(notes))
        assert run.returncode == 2 and "is not a study plan" in run.stderr and run.stdout == ""


def test_a_saved_plan_still_resumes_progress(tmp_path):
    plan = tmp_path / "plan.md"
    assert _run("analyze", PAPER, "--studied", "Probability", "--plan-file", str(plan)).returncode == 0
    run = _run("analyze", PAPER, "--resume", str(plan))
    assert run.returncode == 0 and "Probability (10h, studied)" in run.stdout
