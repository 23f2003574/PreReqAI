import json
from pathlib import Path

import pytest

from backend.cli import main

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"

pytestmark = pytest.mark.prereqai


def _report(capsys, *flags):
    assert main(["prerequisites", "analyze", str(SAMPLE), "--json", *flags]) == 0
    return json.loads(capsys.readouterr().out)["report"]


def test_remaining_hours_equal_total_until_something_is_studied(capsys):
    time = _report(capsys)["study_time"]
    assert time["remaining_hours"] == time["total_hours"] > 0


def test_studied_concepts_reduce_remaining_hours_but_not_the_total(capsys):
    base = _report(capsys)
    plan = base["learning_plan"]
    report = _report(capsys, "--studied", plan[0]["concept"])
    assert report["study_time"]["total_hours"] == base["study_time"]["total_hours"]
    assert report["study_time"]["remaining_hours"] == base["study_time"]["total_hours"] - plan[0]["estimated_hours"]

    done = _report(capsys, *[f for s in plan for f in ("--studied", s["concept"])])
    assert done["study_time"]["remaining_hours"] == 0
