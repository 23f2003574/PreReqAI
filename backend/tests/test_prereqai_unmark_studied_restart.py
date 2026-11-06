"""Unmarking a studied concept over HTTP is saved: after a server restart the concept is still not studied."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai

client = TestClient(app)


def test_an_unmarked_concept_stays_unmarked_after_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    url = f"/api/prerequisites/sessions/{sid}/studied"
    client.post(url, params={"concept": "Probability"})
    client.delete(url, params={"concept": "Probability"})
    session_manager.sessions.clear()  # a new server process: only the saved file remains
    session_manager._last_used.clear()
    after = client.get(f"/api/session/{sid}").json()
    assert not any(item["completed"] for item in after["study_progress"])
    assert after["readiness"]["completed_concepts"] == 0
