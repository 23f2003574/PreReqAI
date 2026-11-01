"""A blank value for a name/path flag (an unset shell variable such as --resume "$PLAN") is a usage error, not a silently
ignored flag; real values still work."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _run(*args):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("command, flag", [
    (["analyze", SAMPLE], "--resume"), (["analyze", SAMPLE], "--plan-file"),
    (["analyze", SAMPLE], "--known"), (["analyze", SAMPLE], "--studied"),
    (["ask", SAMPLE, "What is softmax?"], "--resume"), (["ask", SAMPLE, "What is softmax?"], "--topic"),
    (["ask", SAMPLE, "What is softmax?"], "--known"), (["ask", SAMPLE, "What is softmax?"], "--studied"),
])
@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_value_is_a_usage_error_naming_the_flag(command, flag, blank):
    run = _run(*command, flag, blank)
    assert run.returncode == 2
    assert f"argument {flag}: must not be empty or blank" in run.stderr
    assert run.stdout == ""


def test_real_values_still_work(tmp_path):
    plan = tmp_path / "plan.md"
    run = _run("analyze", SAMPLE, "--studied", "Calculus", "--known", "Probability", "--plan-file", str(plan))
    assert run.returncode == 0 and "(Calculus" not in run.stderr and plan.exists()
    assert _run("ask", SAMPLE, "What is softmax?", "--topic", "Softmax", "--resume", str(plan)).returncode == 0
