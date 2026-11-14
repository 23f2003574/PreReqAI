"""The schedule covers what the learner still has to study, and the daily hours survive a saved plan and an old session."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.study_plan_markdown import hours_per_day_from_plan, plan_markdown

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def started(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    outcome = platform.analyze(SAMPLE, hours_per_day=4)
    yield outcome["session_id"], outcome["report"]
    session_manager.sessions.clear()


def scheduled(study_time):
    return sorted({item["concept"] for day in study_time["schedule"] for item in day["items"]})


def test_a_fresh_session_schedules_its_full_workload(started):
    _, report = started
    plan, time = report["learning_plan"], report["study_time"]
    assert scheduled(time) == sorted(step["concept"] for step in plan)
    assert time["total_hours"] == time["remaining_hours"] == sum(step["estimated_hours"] for step in plan) and time["completed_hours"] == 0
    assert sum(day["hours"] for day in time["schedule"]) == pytest.approx(time["total_hours"]) and time["daily_hours"] == 4


def test_studying_a_concept_shrinks_the_remaining_workload_and_the_schedule(started):
    sid, report = started
    first = report["learning_plan"][0]
    before = report["study_time"]
    after = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": first["concept"]}).json()["study_time"]
    assert first["concept"] not in scheduled(after)
    assert after["total_hours"] == before["total_hours"] and after["completed_hours"] == first["estimated_hours"]
    assert after["remaining_hours"] == before["total_hours"] - first["estimated_hours"]
    assert sum(day["hours"] for day in after["schedule"]) == pytest.approx(after["remaining_hours"])
    assert after["recommended_days"] == len(after["schedule"]) <= before["recommended_days"] and after["daily_hours"] == 4
    undone = client.delete(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": first["concept"]}).json()["study_time"]
    assert undone["schedule"] == before["schedule"] and undone["remaining_hours"] == before["total_hours"]


def test_everything_studied_leaves_no_days_and_a_known_concept_leaves_the_plan(started):
    sid, report = started
    names = [step["concept"] for step in report["learning_plan"]]
    for name in names[1:]:
        done = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": name}).json()["study_time"]
    assert scheduled(done) == [names[0]]
    known = client.post(f"/api/prerequisites/sessions/{sid}/known", params={"concept": names[0]}).json()["study_time"]
    assert names[0] not in scheduled(known) and known["total_hours"] == known["completed_hours"] + known["remaining_hours"]
    assert known["remaining_hours"] == 0 and known["schedule"] == [] and known["recommended_days"] == 0


def test_the_daily_hours_are_saved_in_the_plan_and_restored_on_resume(started, tmp_path):
    sid, report = started
    plan = client.get(f"/api/session/{sid}/plan").text
    assert hours_per_day_from_plan(plan) == 4.0
    resumed = platform.analyze(SAMPLE)["report"]["study_time"]["daily_hours"]
    assert resumed == 3.0  # nothing restored without a plan
    response = client.post("/api/prerequisites/analyze", files={"paper": open(SAMPLE, "rb"), "resume": ("plan.md", plan.encode())})
    assert response.json()["report"]["study_time"]["daily_hours"] == 4.0
    explicit = client.post("/api/prerequisites/analyze", data={"hours_per_day": "2"}, files={"paper": open(SAMPLE, "rb"), "resume": ("plan.md", plan.encode())})
    assert explicit.json()["report"]["study_time"]["daily_hours"] == 2.0


def test_the_hours_survive_when_every_step_is_studied_and_bad_values_are_ignored():
    study_time = {"daily_hours": 5.0, "schedule": [], "total_hours": 10, "recommended_days": 0}
    report = {"paper": {"title": "T"}, "learning_plan": [{"step": 1, "concept": "Calculus", "estimated_hours": 10}], "study_time": study_time,
              "study_progress": [{"concept": "Calculus", "completed": True}]}
    assert hours_per_day_from_plan(plan_markdown(report)) == 5.0
    assert hours_per_day_from_plan("# Study plan: T\nDaily schedule (99h per day, 1 day):") is None
    assert hours_per_day_from_plan("# Study plan: T\nnothing here") is None


def test_a_session_saved_without_the_new_fields_still_reports(started):
    sid, _ = started
    session = session_manager.get(sid)
    for name in ("daily_hours", "schedule"):
        session.paper.study_time.__dict__.pop(name, None)
    session.paper.__dict__.pop("hours_per_day", None)  # saved before the daily hours existed
    answer = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": session.paper.learning_plan[0].concept})
    assert answer.status_code == 200 and answer.json()["study_time"]["daily_hours"] == 3.0
