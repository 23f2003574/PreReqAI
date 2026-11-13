"""The learner's daily study hours set the recommended days and a day-by-day schedule built from the planner's own hour estimates."""
import json
import math
from types import SimpleNamespace as N

import pytest
from fastapi.testclient import TestClient

from backend.cli import main
from backend.main import app
from backend.prerequisites.study_time_estimator import StudyTimeEstimator, build_schedule, parse_hours_per_day, schedule_order
from backend.study_plan_markdown import is_saved_plan, plan_markdown, studied_from_plan

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


def steps(**hours):
    return [N(concept=name, estimated_hours=value) for name, value in hours.items()]


def paper_with(plan, hours_per_day=None, importance=None):
    paper = N(learning_plan=plan, prerequisites=[N(concept=c, importance=i) for c, i in (importance or {}).items()])
    if hours_per_day is not None:
        paper.hours_per_day = hours_per_day
    return StudyTimeEstimator().estimate(paper).study_time


@pytest.mark.parametrize("value", [0, -1, "0", "-2.5", "abc", "", "nan", "inf", float("nan"), float("inf"), True, 24.5, [3]])
def test_invalid_hours_are_rejected_with_a_clear_message(value):
    with pytest.raises(ValueError, match="hours per day"):
        parse_hours_per_day(value)


@pytest.mark.parametrize("value, expected", [(None, 3.0), (2, 2.0), ("1.5", 1.5), (" 4 ", 4.0), (24, 24.0), (0.5, 0.5)])
def test_valid_hours_are_accepted(value, expected):
    assert parse_hours_per_day(value) == expected


def test_the_default_keeps_the_old_three_hours_a_day_estimate():
    for total in range(0, 61):
        study_time = paper_with(steps(A=total) if total else [])
        assert study_time.recommended_days == max(1, (total + 2) // 3) and study_time.daily_hours == 3.0
        assert study_time.average_hours_per_day == round(total / study_time.recommended_days, 1)


def test_the_schedule_fills_days_and_splits_a_step_across_days():
    days = build_schedule(steps(A=5, B=2), 3)
    assert [(d["day"], d["hours"], d["items"]) for d in days] == [
        (1, 3, [{"concept": "A", "hours": 3}]),
        (2, 3, [{"concept": "A", "hours": 2}, {"concept": "B", "hours": 1}]),
        (3, 1, [{"concept": "B", "hours": 1}]),
    ]


@pytest.mark.parametrize("per_day", [0.5, 1, 2, 2.5, 3, 7, 24])
def test_days_and_hours_are_consistent_for_any_daily_time(per_day):
    plan = steps(**{"Linear Algebra": 12, "Probability": 10, "Calculus": 10, "Neural Networks": 15})
    study_time = paper_with(plan, per_day)
    assert study_time.recommended_days == math.ceil(47 / per_day) == len(study_time.schedule)
    assert sum(d["hours"] for d in study_time.schedule) == pytest.approx(47) and all(d["hours"] <= per_day + 1e-9 for d in study_time.schedule)
    assert study_time.daily_hours == per_day


def test_essential_comes_before_supporting_but_never_before_a_dependency():
    plan = steps(**{"Linear Algebra": 12, "Probability": 10, "Calculus": 10, "Neural Networks": 15, "Attention": 8})
    importance = {"Linear Algebra": "supporting", "Probability": "supporting", "Calculus": "supporting", "Neural Networks": "essential", "Attention": "essential"}
    order = [s.concept for s in schedule_order(plan, importance)]
    # Attention needs Linear Algebra and Probability (by the rule table), so they come first; Neural Networks and Calculus have no
    # recorded dependency between them, so the essential one goes first. Supporting Calculus follows once nothing essential is ready.
    assert order.index("Linear Algebra") < order.index("Attention") and order.index("Probability") < order.index("Attention")
    assert order == ["Neural Networks", "Linear Algebra", "Probability", "Attention", "Calculus"]


def test_without_importance_data_the_plan_order_is_kept():
    plan = steps(B=1, A=1, C=1)
    assert [s.concept for s in schedule_order(plan, {})] == ["B", "A", "C"]


def cli_json(capsys, *extra):
    assert main(["prerequisites", "analyze", SAMPLE, "--json", *extra]) == 0
    return json.loads(capsys.readouterr().out)["report"]


def test_cli_hours_per_day_changes_days_and_schedule_and_default_is_three(capsys):
    default, two = cli_json(capsys), cli_json(capsys, "--hours-per-day", "2")
    assert default["study_time"]["daily_hours"] == 3.0 and default["study_time"]["recommended_days"] == len(default["study_time"]["schedule"])
    assert two["study_time"]["daily_hours"] == 2.0 and two["study_time"]["recommended_days"] == math.ceil(two["study_time"]["total_hours"] / 2)
    assert two["study_time"]["total_hours"] == default["study_time"]["total_hours"]


def test_cli_hours_per_day_survives_a_known_concept(capsys):
    report = cli_json(capsys, "--hours-per-day", "2", "--known", "Probability")
    assert report["study_time"]["daily_hours"] == 2.0 and all(i["concept"] != "Probability" for d in report["study_time"]["schedule"] for i in d["items"])


@pytest.mark.parametrize("value", ["0", "-1", "abc", "nan", "inf", "25"])
def test_cli_rejects_invalid_hours(value, capsys):
    with pytest.raises(SystemExit) as stopped:
        main(["prerequisites", "analyze", SAMPLE, "--hours-per-day", value])
    assert stopped.value.code == 2 and "hours per day" in capsys.readouterr().err


def test_the_plan_file_lists_the_daily_schedule_and_resume_still_works(tmp_path, capsys):
    target = tmp_path / "plan.md"
    assert main(["prerequisites", "analyze", SAMPLE, "--hours-per-day", "2", "--plan-file", str(target)]) == 0
    capsys.readouterr()
    text = target.read_text(encoding="utf-8")
    assert is_saved_plan(text) and "Daily schedule (2h per day, 24 days):" in text and "- Day 1 (2h): " in text
    assert studied_from_plan(text) == []
    assert main(["prerequisites", "analyze", SAMPLE, "--resume", str(target), "--json"]) == 0


def test_markdown_without_a_schedule_is_unchanged_for_older_reports():
    report = {"paper": {"title": "T"}, "learning_plan": [{"step": 1, "concept": "Calculus", "estimated_hours": 10}], "study_time": {"total_hours": 10}}
    assert "Daily schedule" not in plan_markdown(report)


def post(**data):
    with open(SAMPLE, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data)


def test_api_accepts_hours_per_day_and_the_session_plan_shows_the_schedule():
    body = post(hours_per_day="2").json()
    assert body["status"] == "success" and body["report"]["study_time"]["daily_hours"] == 2.0
    plan = client.get(f"/api/session/{body['session_id']}/plan").text
    assert "Daily schedule (2h per day" in plan
    assert post().json()["report"]["study_time"]["daily_hours"] == 3.0


@pytest.mark.parametrize("value", ["0", "-3", "abc", "nan", "inf", "30"])
def test_api_rejects_invalid_hours_with_422(value):
    response = post(hours_per_day=value)
    assert response.status_code == 422 and "hours_per_day" in response.json()["detail"]


def test_a_session_saved_without_the_new_fields_still_reports():
    from backend.models import StudyTimeEstimate
    from backend.reporting.learning_report_generator import LearningReportGenerator

    old = StudyTimeEstimate(total_hours=5, recommended_days=2, average_hours_per_day=2.5)
    del old.__dict__["schedule"]  # as unpickled from a file written before the field existed
    assert getattr(old, "schedule", []) == [] and old.daily_hours == 3.0
    assert LearningReportGenerator is not None


def test_a_blank_form_field_counts_as_not_given():
    assert post(hours_per_day="").json()["report"]["study_time"]["daily_hours"] == 3.0
