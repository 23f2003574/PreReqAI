"""A question's conversation is saved with the session; when it cannot be written the answer says so, and when it can it survives a reload."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)
UNSAVED = "could not be saved to PREREQAI_SESSION_DIR"


def _analyze():
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]


def test_a_question_that_cannot_be_saved_warns(tmp_path, monkeypatch):
    sid = _analyze()
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(blocker))
    body = client.post(f"/api/session/{sid}/question", json={"question": "Summarize this paper"}).json()
    assert body["status"] == "success" and any(UNSAVED in w for w in body["warnings"])


def test_a_saved_question_survives_a_reload_without_the_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    sid = _analyze()
    body = client.post(f"/api/session/{sid}/question", json={"question": "Summarize this paper"}).json()
    assert body["status"] == "success" and not any(UNSAVED in w for w in body["warnings"])
    turns = len(session_manager.get(sid).conversation_history)
    assert turns > 0
    session_manager.sessions.clear()  # as after a restart
    assert len(session_manager.get(sid).conversation_history) == turns
