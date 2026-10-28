import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _run(*args):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", *args],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    return run.returncode, run.stdout, run.stderr


@pytest.mark.parametrize("command", [["analyze", "  "], ["ask", "", "What is softmax?"], ["ask", " ", "--json", "x"]])
def test_a_blank_paper_is_a_usage_error_before_any_analysis(command):
    code, out, err = _run(*command)
    assert code == 2 and out == "" and "paper must not be empty" in err and "nothing was analysed" in err


def test_a_real_paper_is_still_analysed_and_a_missing_file_stays_an_analysis_failure():
    assert _run("analyze", SAMPLE)[0] == 0
    code, _, err = _run("analyze", "missing.pdf")
    assert code == 1 and "no such file" in err
