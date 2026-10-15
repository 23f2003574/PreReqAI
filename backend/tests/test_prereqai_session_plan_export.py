"""GET /api/session/{id}/plan returns the study plan as a Markdown checklist, matching the CLI's --plan-file."""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _analyze():
    with open(SAMPLE, "rb") as handle:
        response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")})
    assert response.status_code == 200
    return response.json()["session_id"]


def test_plan_export_ticks_progress_and_links_resources():
    session_id = _analyze()
    first = client.get(f"/api/session/{session_id}/plan")
    assert first.status_code == 200 and first.headers["content-type"].startswith("text/markdown")
    assert first.text.startswith("# Study plan:") and "- [ ] 1. " in first.text and "](https://" in first.text
    assert "[x]" not in first.text

    client.post(f"/api/prerequisites/sessions/{session_id}/studied", params={"concept": "Probability"})
    assert "- [x] 2. Probability" in client.get(f"/api/session/{session_id}/plan").text


def test_plan_export_for_unknown_session_is_404():
    assert client.get("/api/session/does-not-exist/plan").status_code == 404
