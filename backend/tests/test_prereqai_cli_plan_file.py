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


def test_unwritable_plan_file_fails_cleanly(tmp_path):
    run = _run("--plan-file", str(tmp_path / "missing" / "plan.md"))
    assert run.returncode == 1 and "could not save the study plan" in run.stderr
    assert "Traceback" not in run.stderr
