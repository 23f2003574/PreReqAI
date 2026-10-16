from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
client = TestClient(app)


def _session():
    with SAMPLE.open("rb") as handle:
        outcome = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    return outcome["session_id"], outcome["report"]


def test_marking_known_removes_concept_from_plan_and_persists_in_session():
    session_id, report = _session()
    plan = [item["concept"] for item in report["study_progress"]]
    url = f"/api/prerequisites/sessions/{session_id}/known"
    done = client.post(url, params={"concept": f" {plan[0].upper()} "}).json()
    assert done["status"] == "success"
    remaining = [item["concept"] for item in done["report"]["study_progress"]]
    assert plan[0] not in remaining and len(remaining) == len(plan) - 1
    stored = client.get(f"/api/session/{session_id}").json()
    assert plan[0] not in [item["concept"] for item in stored["study_progress"]]


def test_known_reports_unknown_session_and_concept():
    session_id, _ = _session()
    url = f"/api/prerequisites/sessions/{session_id}/known"
    assert client.post("/api/prerequisites/sessions/nope/known", params={"concept": "x"}).status_code == 404
    assert client.post(url, params={"concept": "Cooking"}).status_code == 422
