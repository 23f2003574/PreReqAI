"""A question topic set on a session is saved with it: after a server restart the learner's focus, conversation history
and topic-scoped answers are what they were, and another session of the same paper is not affected."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai

SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"


def _analyze(client):
    with SAMPLE.open("rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]


def _ask(client, sid, question, **extra):
    response = client.post(f"/api/session/{sid}/question", json={"question": question, **extra})
    assert response.status_code == 200
    return response.json()["responses"][0]["answer"]


def test_a_session_topic_and_its_history_survive_a_restart_and_stay_with_that_session(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    client = TestClient(app)
    focused, other = _analyze(client), _analyze(client)

    before = _ask(client, focused, "Quiz me", topic="Softmax")
    assert before.startswith("Softmax Q1")
    history = len(client.get(f"/api/session/{focused}").json()["conversation_history"])

    session_manager.sessions.clear()  # the server restarts: memory is gone

    restored = client.get(f"/api/session/{focused}").json()
    assert restored["active_concept"] == "Softmax"
    assert len(restored["conversation_history"]) == history == 2  # the question and its answer
    assert _ask(client, focused, "Quiz me") == before  # still scoped to the saved topic, without sending it again
    assert client.get(f"/api/session/{other}").json()["active_concept"] is None
    assert _ask(client, other, "Quiz me") != before  # the other session quizzes the paper's concepts, not Softmax alone
