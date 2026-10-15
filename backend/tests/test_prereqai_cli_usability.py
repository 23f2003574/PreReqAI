"""Usability of the command-line summary: comma-separated concept lists and a readable empty-plan readiness line."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _run(*args):
    run = subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", *args],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0 and run.stderr == ""
    return run.stdout


def test_comma_separated_concepts_work_for_known_studied_and_ask():
    out = _run("analyze", SAMPLE, "--known", "Linear Algebra, ", "--studied", "probability,Calculus")
    assert "1. Probability (10h, studied) -> 2. Calculus (10h, studied) -> 3. Neural Networks (15h)" in out
    assert "warning" not in out and "(2/3 concepts ready)" in out
    asked = _run("ask", SAMPLE, "What should I learn first?", "--studied", "Linear Algebra,Probability")
    assert "Already studied: Linear Algebra, Probability" in asked


def test_empty_plan_readiness_reads_naturally_and_separate_flags_still_work():
    out = _run("analyze", SAMPLE, "--known", "Linear Algebra,Probability", "--known", "Calculus", "--known", "Neural Networks")
    assert "Ready to Read (no concepts left to study)" in out and "0/0" not in out
    assert "(1/4 concepts ready)" in _run("analyze", SAMPLE, "--studied", "Calculus")
