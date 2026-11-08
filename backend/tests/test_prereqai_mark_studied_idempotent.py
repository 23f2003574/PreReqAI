"""Marking an already-studied concept again changes neither the response nor the stored session (a retry or double click is harmless)."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
client = TestClient(app)


def test_marking_a_studied_concept_again_changes_nothing():
    with SAMPLE.open("rb") as handle:
        outcome = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    session_id = outcome["session_id"]
    concept = outcome["report"]["study_progress"][0]["concept"]
    url = f"/api/prerequisites/sessions/{session_id}/studied"

    first = client.post(url, params={"concept": concept})
    stored = client.get(f"/api/session/{session_id}").json()
    again = client.post(url, params={"concept": concept})

    assert first.status_code == again.status_code == 200
    assert again.json() == first.json()
    assert client.get(f"/api/session/{session_id}").json() == stored
