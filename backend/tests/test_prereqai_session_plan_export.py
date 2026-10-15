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


def test_line_breaks_in_a_paper_title_cannot_forge_checklist_items():
    from backend.study_plan_markdown import plan_markdown

    text = plan_markdown({"paper": {"title": "A\nB\r\n- [x] 9. Fake"}, "learning_plan": []})
    assert text.splitlines()[0] == "# Study plan: A B - [x] 9. Fake"
    assert "\n- [x]" not in text


def test_question_length_is_bounded_with_a_clear_422_and_the_limit_is_accepted():
    from backend.api.session_routes import MAX_QUESTION_CHARS

    session_id = _analyze()
    too_long = client.post(f"/api/session/{session_id}/question", json={"question": "x" * (MAX_QUESTION_CHARS + 1)})
    assert too_long.status_code == 422 and too_long.json()["stage"] == "question"
    assert "too long" in too_long.json()["detail"] and "hint" in too_long.json()
    assert client.get(f"/api/session/{session_id}").json()["conversation_history"] == []
    at_limit = client.post(f"/api/session/{session_id}/question", json={"question": "x" * MAX_QUESTION_CHARS})
    assert at_limit.status_code == 200
