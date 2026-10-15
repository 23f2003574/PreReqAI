"""Mark/unmark-studied errors use the same failure envelope as every other session endpoint."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"
ENVELOPE = {"status", "stage", "detail", "error", "hint", "warnings"}


def test_unknown_and_unreadable_sessions_and_bad_concepts_use_the_failure_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    bad = "11111111-1111-4111-8111-111111111111"
    (tmp_path / f"{bad}.session").write_bytes(b"garbage")

    for verb in (client.post, client.delete):
        unknown = verb("/api/prerequisites/sessions/22222222-2222-4222-8222-222222222222/studied", params={"concept": "x"})
        assert unknown.status_code == 404 and set(unknown.json()) == ENVELOPE
        assert unknown.json()["status"] == "failure" and unknown.json()["detail"] == "Session not found"
        unreadable = verb(f"/api/prerequisites/sessions/{bad}/studied", params={"concept": "x"})
        assert unreadable.status_code == 404 and unreadable.json()["detail"] == "Session could not be restored"

    with SAMPLE.open("rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    wrong = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Cooking"})
    assert wrong.status_code == 422 and set(wrong.json()) == ENVELOPE
    assert "Cooking" in wrong.json()["detail"] and wrong.json()["stage"] == "study_progress"


def test_success_response_is_unchanged():
    with SAMPLE.open("rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    ok = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Calculus"}).json()
    assert ok["status"] == "success" and ok["session_id"] == sid and ok["readiness"]["completed_concepts"] == 1
