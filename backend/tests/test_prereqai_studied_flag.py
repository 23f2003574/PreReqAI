import json
from pathlib import Path

from backend.cli import main

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


def _run(capsys, *flags):
    assert main(["prerequisites", "analyze", str(SAMPLE), "--json", *flags]) == 0
    return json.loads(capsys.readouterr().out)


def test_studied_concepts_count_toward_readiness_and_stay_in_the_plan(capsys):
    plan = [s["concept"] for s in _run(capsys)["report"]["learning_plan"]]
    out = _run(capsys, "--studied", plan[0].lower(), "--studied", plan[1])
    report = out["report"]
    assert [s["concept"] for s in report["learning_plan"]] == plan
    assert [p["concept"] for p in report["study_progress"] if p["completed"]] == plan[:2]
    assert report["readiness"]["completed_concepts"] == 2 and not report["readiness"]["ready_to_read"]

    done = _run(capsys, *[f for c in plan for f in ("--studied", c)] + ["--studied", "Typo"])
    assert done["report"]["readiness"]["ready_to_read"] is True
    assert done["warnings"] == ["--studied 'Typo' is not in this paper's study plan and was ignored"]


def test_human_summary_shows_the_new_readiness(capsys):
    plan = [s["concept"] for s in _run(capsys)["report"]["learning_plan"]]
    assert main(["prerequisites", "analyze", str(SAMPLE), "--studied", plan[0]]) == 0
    assert f"(1/{len(plan)} concepts ready)" in capsys.readouterr().out
