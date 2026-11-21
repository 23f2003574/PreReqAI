"""Graded reviews through the API: grading a review, the capped schedule, and reviews in the session calendar and its .ics."""
import pytest
from fastapi.testclient import TestClient

from backend import learner_profile
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


def test_grading_a_review_sets_its_ease_and_next_time_and_bad_grades_are_refused(env):
    first = client.post("/api/review/grade", json={"question_id": "Softmax:1", "concept": "Softmax", "grade": "good", "profile": "me"}).json()
    hard = client.post("/api/review/grade", json={"question_id": "Softmax:1", "concept": "Softmax", "grade": "hard", "profile": "me"}).json()
    assert first["status"] == "success" and first["interval_hours"] == 24.0 and hard["ease"] < first["ease"] and hard["grade"] == "hard"
    assert client.post("/api/review/grade", json={"question_id": "Softmax:1", "concept": "Softmax", "grade": "perfect", "profile": "me"}).status_code == 422
    assert client.post("/api/review/grade", json={"question_id": "Softmax:1", "concept": "Softmax", "grade": "good", "profile": "../x"}).status_code == 404


def test_the_schedule_never_exceeds_the_cap_and_the_calendar_and_ics_carry_the_reviews(env):
    path = env / "profiles" / "me.json"
    for i in range(1, 8):
        learner_profile.record_review(path, f"Softmax:{i}", "Softmax", "good", moment=None)
    schedule = client.get("/api/review/schedule", params={"profile": "me", "cap": 3, "days": 30}).json()
    assert schedule["status"] == "success" and all(d["count"] <= 3 for d in schedule["days"]) and sum(d["count"] for d in schedule["days"]) == 7
    assert client.get("/api/review/schedule", params={"profile": "me", "cap": 0}).status_code == 422
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data={"profile": "me"}).json()["session_id"]
    calendar = client.get(f"/api/session/{sid}/calendar", params={"review_cap": 3}).json()
    assert calendar["status"] == "success" and calendar["review_cap"] == 3 and sum(r["count"] for r in calendar["reviews"]) == 7
    assert "SUMMARY:Review" in client.get(f"/api/session/{sid}/calendar.ics").text
