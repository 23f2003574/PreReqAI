import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

client = TestClient(app)


def _analyze():
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        body = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    return body["session_id"], body["report"]


def test_studying_a_concept_updates_the_time_left_on_the_session():
    session_id, report = _analyze()
    first = report["learning_plan"][0]
    base = f"/api/prerequisites/sessions/{session_id}"
    total = report["study_time"]["total_hours"]
    assert client.get(f"/api/session/{session_id}").json()["study_time"]["remaining_hours"] == total

    studied = client.post(f"{base}/studied", params={"concept": first["concept"]}).json()
    left = total - first["estimated_hours"]
    assert studied["study_time"]["remaining_hours"] == left
    assert client.get(f"/api/session/{session_id}").json()["study_time"] == studied["study_time"]

    undone = client.delete(f"{base}/studied", params={"concept": first["concept"]}).json()
    assert undone["study_time"]["remaining_hours"] == total


def test_a_rejected_concept_leaves_the_time_left_unchanged():
    session_id, report = _analyze()
    bad = client.post(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": "Cooking"})
    assert bad.status_code == 422 and "study_time" not in bad.json()
    assert client.get(f"/api/session/{session_id}").json()["study_time"] == report["study_time"]
