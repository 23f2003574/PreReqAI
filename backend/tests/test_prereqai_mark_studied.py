from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
client = TestClient(app)


def _analyze():
    with SAMPLE.open("rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()


def test_studying_every_planned_concept_moves_readiness_to_ready():
    outcome = _analyze()
    session_id = outcome["session_id"]
    plan = [item["concept"] for item in outcome["report"]["study_progress"]]
    assert plan and outcome["report"]["readiness"]["progress_percent"] == 0

    first = client.post(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": plan[0]}).json()
    assert first["readiness"]["completed_concepts"] == 1 and not first["readiness"]["ready_to_read"]
    assert [p["completed"] for p in first["study_progress"]][0] is True

    for concept in plan[1:]:
        last = client.post(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": concept}).json()
    assert last["readiness"]["ready_to_read"] and last["readiness"]["status"] == "Ready to Read"


def test_unknown_session_and_unknown_concept_are_reported():
    session_id = _analyze()["session_id"]
    assert client.post("/api/prerequisites/sessions/nope/studied", params={"concept": "x"}).status_code == 404
    assert client.post(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": "Cooking"}).status_code == 422
