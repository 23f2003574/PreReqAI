"""POST /api/prerequisites/analyze accepts a saved plan as `resume`, restoring studied and known concepts (as the CLI's --resume does)."""
from starlette.testclient import TestClient

from backend.main import app

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _analyze(client, **extra):
    with open(SAMPLE, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf"), **extra})


def test_saved_plan_restores_studied_and_known_over_http():
    client = TestClient(app)
    first = _analyze(client).json()["session_id"]
    base = f"/api/prerequisites/sessions/{first}"
    client.post(base + "/studied", params={"concept": "Probability"})
    client.post(base + "/known", params={"concept": "Calculus"})
    plan = client.get(f"/api/session/{first}/plan").text

    resumed = _analyze(client, resume=("plan.md", plan.encode(), "text/markdown"))
    assert resumed.status_code == 200
    report = client.get(f"/api/session/{resumed.json()['session_id']}").json()
    progress = {item["concept"]: item["completed"] for item in report["study_progress"]}
    assert progress["Probability"] is True
    assert "Calculus" not in progress


def test_resume_that_is_not_a_saved_plan_is_rejected():
    client = TestClient(app)
    response = _analyze(client, resume=("notes.md", b"just some notes", "text/markdown"))
    assert response.status_code == 422
    assert "not a study plan" in response.json()["detail"]
