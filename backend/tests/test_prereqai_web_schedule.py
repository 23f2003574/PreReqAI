"""The web page lets a learner set their daily study hours, shows the server's schedule, restores the setting and follows progress."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield
    session_manager.sessions.clear()


def analyse(**fields):
    with open(SAMPLE, "rb") as paper:
        return client.post("/api/prerequisites/analyze", data=fields, files={"paper": paper})


def test_the_page_has_an_hours_input_sends_it_and_draws_the_servers_schedule_without_calculating_one():
    for fragment in ('id="hours"', 'name="hours_per_day"', 'type="number"', 'data.append("hours_per_day", hours)', "function renderSchedule()",
                     'id="schedule"', 'id="schedulesummary"', "st.schedule", "st.remaining_hours", "st.daily_hours", "renderSchedule();",
                     "Daily study hours must be a number above 0 and at most 24.", "saved by an older version and has no schedule"):
        assert fragment in PAGE, fragment
    assert "innerHTML" not in PAGE and "Math.ceil" not in PAGE and "hoursPerDay" not in PAGE  # no scheduling arithmetic in the page


def test_the_selected_hours_reach_the_backend_and_the_schedule_the_page_reads_matches_them():
    study_time = analyse(hours_per_day="4").json()["report"]["study_time"]
    assert study_time["daily_hours"] == 4.0
    days = study_time["schedule"]
    assert all({"day", "hours", "items"} <= set(day) and day["hours"] <= 4.0 for day in days)
    assert {"total_hours", "remaining_hours", "completed_hours", "recommended_days"} <= set(study_time) and study_time["recommended_days"] == len(days)
    assert sum(day["hours"] for day in days) == pytest.approx(study_time["total_hours"])
    assert analyse().json()["report"]["study_time"]["daily_hours"] == 3.0  # an empty box sends nothing: the default


@pytest.mark.parametrize("value", ["0", "-2", "25", "abc", "nan"])
def test_invalid_hours_are_refused_with_the_detail_and_hint_the_page_shows(value):
    response = analyse(hours_per_day=value)
    body = response.json()
    assert response.status_code == 422 and body["status"] == "failure" and "hours_per_day" in body["detail"] and body["hint"]
    assert 'typeof body.detail === "string"' in PAGE and "body && body.hint" in PAGE  # what failureText reads


def test_a_restored_session_carries_the_saved_hours_and_schedule_and_progress_refreshes_it():
    sid = analyse(hours_per_day="5").json()["session_id"]
    first = client.get(f"/api/session/{sid}").json()["study_time"]["schedule"][0]["items"][0]["concept"]
    session_manager.sessions.clear()  # a reload after a server restart
    restored = client.get(f"/api/session/{sid}").json()["study_time"]
    assert restored["daily_hours"] == 5.0 and restored["schedule"] and first in {i["concept"] for d in restored["schedule"] for i in d["items"]}
    updated = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": first}).json()["study_time"]
    assert first not in {i["concept"] for d in updated["schedule"] for i in d["items"]} and updated["daily_hours"] == 5.0
    assert updated["remaining_hours"] < restored["remaining_hours"] and updated["completed_hours"] > 0
    assert 'state.studyTime = body.study_time || state.studyTime' in PAGE and "renderMeta();" in PAGE  # the page redraws after the response


def test_a_session_without_schedule_data_still_restores_and_the_page_says_so():
    sid = analyse().json()["session_id"]
    session = session_manager.get(sid)
    for name in ("schedule", "daily_hours"):
        session.report["study_time"].pop(name, None)
    restored = client.get(f"/api/session/{sid}")
    assert restored.status_code == 200 and "schedule" not in restored.json()["study_time"]
    assert "No schedule is available for this session" in PAGE and "Array.isArray(st.schedule)" in PAGE
