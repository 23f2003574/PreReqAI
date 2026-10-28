import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _summary(*flags):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", SAMPLE, *flags],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    return next(line for line in run.stdout.splitlines() if "preparation:" in line)


def test_a_single_preparation_day_is_not_pluralised():
    line = _summary("--known", "Linear Algebra", "--known", "Probability", "--known", "Calculus", "--known", "Neural Networks")
    assert "over 1 day" in line and "1 days" not in line


def test_several_days_stay_plural():
    assert "over 16 days" in _summary()
