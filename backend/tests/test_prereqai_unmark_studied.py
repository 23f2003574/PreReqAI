from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
client = TestClient(app)


def _session():
    with SAMPLE.open("rb") as handle:
        outcome = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    return outcome["session_id"], [item["concept"] for item in outcome["report"]["study_progress"]]


def test_unmarking_restores_progress_and_readiness():
    session_id, plan = _session()
    url = f"/api/prerequisites/sessions/{session_id}/studied"
    marked = client.post(url, params={"concept": plan[0]}).json()
    assert marked["readiness"]["completed_concepts"] == 1

    undone = client.delete(url, params={"concept": plan[0]}).json()
    assert undone["status"] == "success"
    assert undone["readiness"]["completed_concepts"] == 0 and undone["readiness"]["progress_percent"] == 0
    assert not any(item["completed"] for item in undone["study_progress"])
    assert not any(item["completed"] for item in client.get(f"/api/session/{session_id}").json()["study_progress"])


def test_concept_names_match_ignoring_case_and_spaces():
    session_id, plan = _session()
    url = f"/api/prerequisites/sessions/{session_id}/studied"
    done = client.post(url, params={"concept": f"  {plan[0].upper()} "}).json()
    assert done["readiness"]["completed_concepts"] == 1
    assert client.delete(url, params={"concept": plan[0].lower()}).json()["readiness"]["completed_concepts"] == 0


def test_unmark_reports_unknown_session_and_concept_and_is_idempotent():
    session_id, plan = _session()
    url = f"/api/prerequisites/sessions/{session_id}/studied"
    assert client.delete("/api/prerequisites/sessions/nope/studied", params={"concept": "x"}).status_code == 404
    assert client.delete(url, params={"concept": "Cooking"}).status_code == 422
    assert client.delete(url, params={"concept": plan[0]}).json()["readiness"]["completed_concepts"] == 0
