"""`analyze --resources` lists a study link for each concept still to study."""
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


def test_resources_listed_for_each_concept_to_study():
    out = _summary("--resources")
    assert "  resources:" in out
    assert "Linear Algebra: MIT 18.06 Linear Algebra (MIT OpenCourseWare, ~12h) https://ocw.mit.edu/" in out
    assert "Neural Networks:" in out


def test_default_summary_has_no_resources_and_studied_concepts_are_skipped():
    assert "resources" not in _summary()
    out = _summary("--resources", "--studied", "Probability")
    assert "Probability:" not in out and "Calculus:" in out


def test_everything_studied_says_nothing_is_left():
    out = _summary("--resources", "--studied", "Linear Algebra", "--studied", "Probability",
                   "--studied", "Calculus", "--studied", "Neural Networks")
    assert "resources: none left to study" in out


def test_resources_follow_the_study_plan_order():
    out = _summary("--resources", "--known", "Linear Algebra")
    plan = [c for c in ("Probability", "Calculus", "Neural Networks") if f"    {c}:" in out]
    listed = [line.split(":")[0].strip() for line in out.splitlines() if line.startswith("    ")]
    assert plan == listed == ["Probability", "Calculus", "Neural Networks"]
