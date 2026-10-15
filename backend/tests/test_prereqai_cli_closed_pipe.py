"""Quitting a pager or `| head` on the CLI's output must not print a BrokenPipeError traceback."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_closing_stdout_early_ends_quietly():
    proc = subprocess.Popen([sys.executable, "-m", "backend.cli", "prerequisites", "analyze",
                             "examples/prerequisites/sample-paper.pdf", ],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    proc.stdout.close()  # the reader goes away while the analysis runs, before the first line is printed
    stderr = proc.stderr.read()
    proc.wait(timeout=60)
    assert "Traceback" not in stderr and "BrokenPipeError" not in stderr
    assert proc.returncode in (0, 141)
