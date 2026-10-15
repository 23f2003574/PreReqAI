"""Acceptance: analyse -> study -> export the plan -> server restart -> the exported plan keeps the learner's progress."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _analyze(**data):
    with open(SAMPLE, "rb") as handle:
        response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data)
    assert response.status_code == 200
    return response.json()["session_id"]


def _ticked(markdown):
    return [line.split(". ", 1)[1].split(" (")[0] for line in markdown.splitlines() if line.startswith("- [x]")]


def test_exported_plan_keeps_progress_across_a_restart_and_ends_with_the_session(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_id = _analyze(known="Calculus")
    plan = client.get(f"/api/session/{session_id}/plan").text
    assert "Calculus" not in plan and _ticked(plan) == []

    for concept in ("Probability", "Neural Networks"):
        assert client.post(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": concept}).status_code == 200
    assert client.delete(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": "Neural Networks"}).status_code == 200

    session_manager.sessions.clear()  # a restart: only the saved file remains
    restored = client.get(f"/api/session/{session_id}/plan")
    assert restored.status_code == 200
    assert _ticked(restored.text) == ["Probability"] and "- [ ] 3. Neural Networks" in restored.text

    assert client.delete(f"/api/session/{session_id}").status_code == 200
    assert client.get(f"/api/session/{session_id}/plan").status_code == 404


def test_plan_of_a_session_with_an_unreadable_saved_file_is_404_with_a_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_id = _analyze()
    session_manager.sessions.clear()
    (tmp_path / f"{session_id}.session").write_bytes(b"not a session")
    response = client.get(f"/api/session/{session_id}/plan")
    assert response.status_code == 404 and response.json()["status"] == "failure" and "hint" in response.json()
