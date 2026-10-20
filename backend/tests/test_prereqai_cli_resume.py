"""`analyze --resume PLAN_FILE` restores the progress ticked in a plan saved earlier."""
import json
import subprocess
import sys
from pathlib import Path

from backend.study_plan_markdown import plan_markdown, studied_from_plan

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _run(*flags):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", SAMPLE, *flags],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def _studied(run):
    report = json.loads(run.stdout)["report"]
    return sorted(item["concept"] for item in report["study_progress"] if item["completed"])


def test_ticked_concepts_are_read_back_from_a_saved_plan():
    report = {
        "paper": {"title": "T"},
        "learning_plan": [{"step": 1, "concept": "Probability (basics)", "estimated_hours": 3}, {"step": 2, "concept": "Calculus", "estimated_hours": 2}],
        "study_progress": [{"concept": "Probability (basics)", "completed": True}],
    }
    assert studied_from_plan(plan_markdown(report)) == ["Probability (basics)"]


def test_resume_carries_progress_over_to_a_new_run_and_combines_with_studied(tmp_path):
    plan = tmp_path / "plan.md"
    assert _run("--studied", "Probability", "--plan-file", str(plan)).returncode == 0
    assert _studied(_run("--resume", str(plan), "--json")) == ["Probability"]
    assert _studied(_run("--resume", str(plan), "--studied", "Calculus", "--plan-file", str(plan), "--json")) == ["Calculus", "Probability"]
    assert studied_from_plan(plan.read_text(encoding="utf-8")) == ["Probability", "Calculus"]  # the same file keeps growing


def test_unreadable_resume_file_is_refused_with_a_hint(tmp_path):
    run = _run("--resume", str(tmp_path / "missing.md"))
    assert run.returncode == 2 and "cannot read the saved plan" in run.stderr and "hint:" in run.stderr
    assert run.stdout == "" and "Traceback" not in run.stderr


def _ask(*flags):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "ask", SAMPLE, "What should I learn first?", *flags],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_ask_answers_from_the_progress_restored_by_resume(tmp_path):
    plan = tmp_path / "plan.md"
    assert _run("--studied", "Probability", "--plan-file", str(plan)).returncode == 0
    run = _ask("--resume", str(plan))
    assert run.returncode == 0 and "Already studied: Probability" in run.stdout
    assert "Already studied" not in _ask().stdout  # without it, the new run starts from nothing


def test_ask_refuses_an_unreadable_resume_file(tmp_path):
    run = _ask("--resume", str(tmp_path / "missing.md"))
    assert run.returncode == 2 and "cannot read the saved plan" in run.stderr and run.stdout == ""
