"""`ask` honours --max-file-mb / --max-seconds like `analyze`: same wording, same exit codes."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _ask(*flags):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", SAMPLE, "Why calculus?", *flags],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_oversized_paper_is_refused_with_the_limit_exit_code():
    run = _ask("--max-file-mb", "0.0001")
    assert run.returncode == 123 and "limit exceeded" in run.stderr and "hint:" in run.stderr and run.stdout == ""


def test_generous_limits_still_answer():
    run = _ask("--max-file-mb", "5", "--max-seconds", "60")
    assert run.returncode == 0 and "Calculus" in run.stdout


def test_invalid_limit_is_refused_without_an_answer():
    run = _ask("--max-seconds", "-1")
    assert run.returncode != 0 and "greater than 0" in run.stderr and run.stdout == ""
