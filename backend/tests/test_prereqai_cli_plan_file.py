"""`analyze --plan-file` saves the study plan as a Markdown checklist."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _run(*flags):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", SAMPLE, *flags],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_plan_file_is_a_checklist_with_progress_and_links(tmp_path):
    target = tmp_path / "plan.md"
    run = _run("--studied", "Probability", "--plan-file", str(target))
    assert run.returncode == 0 and f"plan saved: {target}" in run.stdout
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# Study plan: Attention Is All You Need")
    assert "[x]" in text and "Probability" in text.split("[x]")[1].splitlines()[0]
    assert "- [ ] " in text and "](https://" in text


def test_unwritable_plan_file_is_refused_before_analysing_with_a_hint(tmp_path):
    for bad, reason in ((tmp_path / "missing" / "plan.md", "does not exist"), (tmp_path, "is a directory")):
        run = _run("--plan-file", str(bad))
        assert run.returncode == 2 and reason in run.stderr and "hint:" in run.stderr
        assert run.stdout == "" and "Traceback" not in run.stderr  # nothing was analysed


def test_plan_file_is_written_with_json_and_stdout_stays_json(tmp_path):
    import json

    target = tmp_path / "plan.md"
    run = _run("--json", "--plan-file", str(target))
    assert run.returncode == 0
    assert json.loads(run.stdout)["status"] == "success"
    assert target.read_text(encoding="utf-8").startswith("# Study plan:")


def test_plan_markdown_summarises_progress_and_hours_left():
    from backend.study_plan_markdown import plan_markdown
    report = {"paper": {"title": "T"}, "learning_plan": [
        {"step": 1, "concept": "A", "estimated_hours": 4}, {"step": 2, "concept": "B", "estimated_hours": 6}],
        "study_progress": [{"concept": "A", "completed": True}], "learning_resources": []}
    assert "1 of 2 studied, about 6h left." in plan_markdown(report).splitlines()
    report["study_progress"] = [{"concept": "A", "completed": True}, {"concept": "B", "completed": True}]
    assert "2 of 2 studied, about 0h left." in plan_markdown(report)
    report["learning_plan"] = []  # boundary: nothing planned, no summary line
    text = plan_markdown(report)
    assert "studied" not in text and "Nothing left to study" in text
