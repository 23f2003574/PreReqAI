"""A saved plan remembers the concepts the learner said they already know, so --resume does not put them back."""
import subprocess
import sys
from pathlib import Path

from backend.study_plan_markdown import known_from_plan, plan_markdown, studied_from_plan

ROOT = Path(__file__).resolve().parents[2]
PAPER = "examples/prerequisites/sample-paper.pdf"


def _run(*args):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_plan_markdown_records_known_concepts_and_reads_them_back():
    report = {"paper": {"title": "T"}, "learning_plan": [], "study_progress": [],
              "missing_prerequisites": [{"concept": "Calculus", "satisfied": True, "reason": "Already known (reported by the learner)"},
                                        {"concept": "Attention", "satisfied": True, "reason": "Covered within the paper"}]}
    text = plan_markdown(report)
    assert "Already known: Calculus" in text and "Attention" not in text.split("Already known:")[1].splitlines()[0]
    assert known_from_plan(text) == ["Calculus"] and studied_from_plan(text) == []
    assert known_from_plan("# Study plan: T\n") == []


def test_resume_keeps_a_known_concept_out_of_the_plan(tmp_path):
    plan = tmp_path / "plan.md"
    first = _run("analyze", PAPER, "--known", "Calculus", "--studied", "Probability", "--plan-file", str(plan))
    assert first.returncode == 0 and "Calculus" not in first.stdout.split("study plan:")[1].splitlines()[0]

    resumed = _run("analyze", PAPER, "--resume", str(plan))
    line = resumed.stdout.split("study plan:")[1].splitlines()[0]
    assert resumed.returncode == 0 and "Calculus" not in line and "Probability (10h, studied)" in line
    assert "warning" not in resumed.stdout

    answer = _run("ask", PAPER, "How long will this take?", "--resume", str(plan))
    assert answer.stdout.splitlines()[0] == "Plan about 27 hours of preparation, roughly 10 days at 2.8 hours a day."
