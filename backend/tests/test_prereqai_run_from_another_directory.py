"""The README's first-run instruction for a directory other than the repository root really works."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples/prerequisites/sample-paper.pdf"
ARGS = [sys.executable, "-m", "backend.cli", "prerequisites", "analyze", str(SAMPLE)]


def _run(cwd, pythonpath):
    env = {**os.environ, "PYTHONPATH": pythonpath}
    return subprocess.run(ARGS, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)


def test_pointing_pythonpath_at_the_checkout_runs_the_quickstart_from_any_directory(tmp_path):
    run = _run(tmp_path, str(ROOT))
    assert run.returncode == 0 and run.stdout.startswith("Analysed 'Attention Is All You Need")


def test_without_it_the_failure_is_the_one_the_readme_tells_the_reader_to_expect(tmp_path):
    run = _run(tmp_path, "")
    assert run.returncode != 0 and "No module named 'backend'" in run.stderr
    readme = (ROOT / "README.md").read_text()
    assert "No module named 'backend'" in readme and "PYTHONPATH=/path/to/PreReqAI" in readme and "--app-dir /path/to/PreReqAI" in readme
