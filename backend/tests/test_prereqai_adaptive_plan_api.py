"""The adaptive plan through the API the page calls: a graded assessment changes the plan, each change has its reason, an override reverses it and survives a reload."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor import diagnostic, quiz_session

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def answer_correctly(sid, concept, times):
    for _ in range(times):
        question = client.get(f"/api/session/{sid}/diagnostic/question", params={"concept": concept}).json()
        options = question["options"]
        correct = options.index(quiz_session._lookup(question["question_id"])[2]["answer"])
        result = client.post(f"/api/session/{sid}/diagnostic/answer", json={"question_id": question["question_id"], "choice": correct, "confidence": "medium"}).json()
        assert result["verdict"]["correct"] is True


def test_the_assessment_serves_graded_questions_for_plan_steps_without_their_answers(sid):
    body = client.get(f"/api/session/{sid}/adaptive-plan/assessment").json()
    assert body["status"] == "success" and body["questions"] and all(len(q["options"]) == 4 and "answer" not in q for q in body["questions"])


def test_correct_answers_shorten_a_step_and_an_override_reverses_it_and_is_remembered(sid):
    before = client.get(f"/api/session/{sid}/adaptive-plan").json()
    assert before["adjustments"] == [] and before["hours_before"] == before["hours_after"]
    step = next(p["concept"] for p in before["plan"] if p["concept"] in quiz_session.ASKABLE and len(quiz_session.ASKABLE[p["concept"]]) >= 2)
    answer_correctly(sid, step, 4)
    after = client.get(f"/api/session/{sid}/adaptive-plan").json()
    changed = next(a for a in after["adjustments"] if a["concept"] == step)
    assert changed["action"] == "compress" and changed["adjusted_hours"] < changed["original_hours"] and changed["reason"] and after["hours_after"] < after["hours_before"]
    client.post(f"/api/session/{sid}/adaptive-plan/override", json={"concept": step, "action": "reject"})
    session_manager.sessions.clear()  # a reload: the choice was saved with the session
    rejected = next(a for a in client.get(f"/api/session/{sid}/adaptive-plan").json()["adjustments"] if a["concept"] == step)
    assert rejected["overridden"] is True and rejected["adjusted_hours"] == rejected["original_hours"]
    client.post(f"/api/session/{sid}/adaptive-plan/override", json={"concept": step, "action": "restore"})
    assert next(a for a in client.get(f"/api/session/{sid}/adaptive-plan").json()["adjustments"] if a["concept"] == step)["overridden"] is False


def test_bad_requests_get_structured_errors_and_the_page_is_wired(sid):
    assert client.post(f"/api/session/{sid}/adaptive-plan/override", json={"concept": "Nope", "action": "reject"}).status_code == 404
    assert client.post(f"/api/session/{sid}/adaptive-plan/override", json={"concept": "Calculus", "action": "burn"}).status_code == 422
    assert client.get(f"/api/session/{sid}/adaptive-plan", params={"deadline": "soon"}).status_code == 422
    assert client.get("/api/session/missing/adaptive-plan").status_code == 404
    assert 'id="adaptivepanel"' in PAGE and "adaptive-plan/override" in PAGE and "diagnostic/answer" in PAGE and "Keep my original hours" in PAGE
