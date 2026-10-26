"""--plan-file never overwrites an existing file that is not a saved study plan (a mistyped path must not destroy the paper)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "examples/prerequisites/sample-paper.pdf"


def _analyze(paper, plan):
    return subprocess.run([sys.executable, "-m", "backend.cli", "prerequisites", "analyze", str(paper), "--plan-file", str(plan)],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_pointing_plan_file_at_the_paper_is_refused_and_the_paper_survives(tmp_path):
    paper = tmp_path / "mine.pdf"
    paper.write_bytes(PAPER.read_bytes())
    run = _analyze(paper, paper)
    assert run.returncode == 2 and "not a saved study plan" in run.stderr and "Analysed" not in run.stdout
    assert paper.read_bytes() == PAPER.read_bytes()


def test_a_new_an_empty_and_an_existing_plan_can_still_be_written(tmp_path):
    for name, before in (("new.md", None), ("empty.md", b""), ("old.md", b"# Study plan: Old\n- [x] 1. Calculus (~10h)\n")):
        plan = tmp_path / name
        if before is not None:
            plan.write_bytes(before)
        assert _analyze(PAPER, plan).returncode == 0
        assert plan.read_text(encoding="utf-8").startswith("# Study plan: Attention Is All You Need")
