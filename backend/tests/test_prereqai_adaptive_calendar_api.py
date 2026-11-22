"""The calendar, .ics and plan text endpoints use the adapted hours by default and the original ones with adapted=false."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor import quiz_session

pytestmark = pytest.mark.prereqai
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze("examples/prerequisites/sample-paper.pdf")["session_id"]
    session_manager.sessions.clear()


def test_adapted_hours_reach_the_calendar_ics_and_plan(sid):
    plan = client.get(f"/api/session/{sid}/adaptive-plan").json()["plan"]
    step = next(p["concept"] for p in plan if p["concept"] in quiz_session.ASKABLE and len(quiz_session.ASKABLE[p["concept"]]) >= 2)
    for _ in range(4):
        q = client.get(f"/api/session/{sid}/diagnostic/question", params={"concept": step}).json()
        right = q["options"].index(quiz_session._lookup(q["question_id"])[2]["answer"])
        client.post(f"/api/session/{sid}/diagnostic/answer", json={"question_id": q["question_id"], "choice": right, "confidence": "medium"})
    after = client.get(f"/api/session/{sid}/adaptive-plan").json()
    adapted = client.get(f"/api/session/{sid}/calendar", params={"today": "2026-12-01", "hours_per_day": 24}).json()
    original = client.get(f"/api/session/{sid}/calendar", params={"today": "2026-12-01", "hours_per_day": 24, "adapted": "false"}).json()
    assert round(sum(d["hours"] for d in adapted["days"]), 2) == after["hours_after"] < after["hours_before"] == round(sum(d["hours"] for d in original["days"]), 2)
    assert step in adapted["adapted_concepts"] and "adapted_concepts" not in original
    assert "adapted to your assessed answers" in client.get(f"/api/session/{sid}/calendar.ics", params={"today": "2026-12-01"}).text
    assert f"(~{next(p['hours'] for p in after['plan'] if p['concept'] == step)}h)" in client.get(f"/api/session/{sid}/plan").text
