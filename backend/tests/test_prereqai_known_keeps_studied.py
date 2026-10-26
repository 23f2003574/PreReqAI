"""A concept studied, then marked known, then un-marked known comes back still studied (progress is not lost)."""
from starlette.testclient import TestClient

from backend.main import app


def _progress(client, sid):
    return {item["concept"]: item["completed"] for item in client.get(f"/api/session/{sid}").json()["study_progress"]}


def test_unmarking_known_restores_the_concepts_earlier_study_progress():
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")},
                          data={"studied": ["Probability"]}).json()["session_id"]
    base = f"/api/prerequisites/sessions/{sid}"
    assert client.post(base + "/known", params={"concept": "Probability"}).status_code == 200
    assert "Probability" not in _progress(client, sid)
    assert client.delete(base + "/known", params={"concept": "Probability"}).status_code == 200
    assert _progress(client, sid)["Probability"] is True
    assert client.get(f"/api/session/{sid}").json()["readiness"]["completed_concepts"] == 1


def test_unmarking_known_of_a_never_studied_concept_stays_unstudied():
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    base = f"/api/prerequisites/sessions/{sid}"
    client.post(base + "/known", params={"concept": "Probability"})
    client.delete(base + "/known", params={"concept": "Probability"})
    assert _progress(client, sid)["Probability"] is False
