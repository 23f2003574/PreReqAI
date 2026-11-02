"""examples/prerequisites/study_journey.py needs httpx2, which the runtime-only requirements.txt does not install:
without it the example must stop with an actionable message, not a raw traceback."""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "examples/prerequisites/study_journey.py"
BLOCK_HTTPX2 = "import sys, runpy; sys.modules['httpx2'] = None; runpy.run_path(sys.argv[1], run_name='__main__')"


def test_a_missing_httpx2_gives_an_install_hint_and_no_traceback():
    run = subprocess.run([sys.executable, "-c", BLOCK_HTTPX2, SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 1
    assert "pip install httpx2" in run.stderr and "requirements-dev.txt" in run.stderr
    assert "Traceback" not in run.stderr and run.stdout == ""


def test_with_httpx2_the_journey_still_runs():
    run = subprocess.run([sys.executable, SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0 and run.stdout.startswith("Study plan: ")


def test_the_examples_readme_tells_the_reader_to_install_it():
    readme = (ROOT / "examples/prerequisites/README.md").read_text(encoding="utf-8")
    assert readme.index("pip install httpx2") < readme.index("python examples/prerequisites/study_journey.py")
