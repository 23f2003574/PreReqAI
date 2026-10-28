import json
from pathlib import Path

import pytest

from backend.cli import main

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
OTHER = "# Study plan: Some Other Paper\n\n- [x] 1. Probability (~10h)\n"

pytestmark = pytest.mark.prereqai


def _run(capsys, *flags):
    assert main(["prerequisites", "analyze", str(SAMPLE), "--json", *flags]) == 0
    return json.loads(capsys.readouterr().out)


def test_a_plan_saved_for_another_paper_is_not_overwritten_by_resuming_into_it(tmp_path, capsys):
    plan = tmp_path / "plan.md"
    plan.write_text(OTHER, encoding="utf-8")
    out = _run(capsys, "--resume", str(plan), "--plan-file", str(plan))
    assert plan.read_text(encoding="utf-8") == OTHER
    assert any("was not overwritten" in warning for warning in out["warnings"])


def test_a_separate_plan_file_and_a_matching_paper_are_still_saved(tmp_path, capsys):
    plan, copy = tmp_path / "plan.md", tmp_path / "copy.md"
    plan.write_text(OTHER, encoding="utf-8")
    _run(capsys, "--resume", str(plan), "--plan-file", str(copy))
    assert copy.read_text(encoding="utf-8").startswith("# Study plan: Attention Is All You Need")

    _run(capsys, "--resume", str(copy), "--plan-file", str(copy), "--studied", "Calculus")
    assert "[x]" in copy.read_text(encoding="utf-8") and "Calculus" in copy.read_text(encoding="utf-8")
