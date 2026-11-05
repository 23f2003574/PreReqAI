"""An unexpected error inside a session route reaches the client as the failure envelope, with the underlying error named."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform

pytestmark = pytest.mark.prereqai

PAPER = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


def _session(client):
    with open(PAPER, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]


def test_an_unexpected_rebuild_error_is_a_readable_failure_envelope(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    session_id = _session(client)

    def exploded(*args, **kwargs):
        raise RuntimeError("rebuild exploded")

    monkeypatch.setattr(platform, "mark_concept_known", exploded)
    response = client.post(f"/api/prerequisites/sessions/{session_id}/known", params={"concept": "calculus"})

    assert response.status_code == 500
    body = response.json()
    assert body["status"] == "failure" and body["stage"] == "server"
    assert body["error"] == {"type": "RuntimeError", "message": "rebuild exploded"}
    assert body["hint"]


def test_expected_errors_keep_their_own_envelope(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    session_id = _session(client)
    response = client.post(f"/api/prerequisites/sessions/{session_id}/known", params={"concept": "no such concept"})
    assert response.status_code == 422 and response.json()["stage"] == "study_progress"
