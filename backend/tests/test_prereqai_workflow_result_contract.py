"""The public result envelope of the PreReqAI workflow endpoints: callers read
status, stage, output, warnings and failure information the same way."""
import json

import pymupdf as fitz
from fastapi.testclient import TestClient

from backend.api.workflow_result import json_violations, failure_response, success_body
from backend.main import app

client = TestClient(app)


def _pdf() -> bytes:
    document = fitz.open()
    document.new_page().insert_text(
        (72, 72), "Attention Is All You Need\n\nAbstract\nWe propose the Transformer.\n\n1 Introduction\nWe use softmax.\n", fontsize=11
    )
    return document.tobytes()


def test_a_successful_analysis_has_status_stage_output_and_warnings():
    response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", _pdf(), "application/pdf")})

    body = response.json()
    assert response.status_code == 200 and body["status"] == "success" and body["stage"] == "session_created"
    assert body["warnings"] == [] and body["feature"] == "Prerequisite Explorer"
    assert {"session_id", "report"} <= set(body) and "error" not in body  # the earlier success keys are preserved


def test_a_failed_analysis_has_the_same_envelope_with_actionable_failure_information():
    response = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", b"not a pdf", "application/pdf")})

    body = response.json()
    assert response.status_code == 400 and body["status"] == "failure" and body["stage"] == "analysis"
    assert body["detail"].startswith("Failed to process the uploaded paper")  # existing clients still read `detail`
    assert body["error"]["type"] and body["error"]["message"] and body["hint"] == "Upload a text-based PDF research paper."
    assert body["warnings"] == [] and "session_id" not in body


def test_unknown_sessions_use_the_same_failure_envelope_on_both_session_endpoints():
    for response in (
        client.get("/api/session/missing"),
        client.post("/api/session/missing/question", json={"question": "x"}),
    ):
        body = response.json()
        assert response.status_code == 404 and body["status"] == "failure" and body["stage"] == "session_lookup"
        assert body["detail"] == "Session not found" and body["hint"] and body["error"]["message"] == "Session not found"


def test_envelope_helpers_always_carry_the_same_keys():
    ok = success_body("Feature", "done", answer=1)
    failed = failure_response(422, "input", "bad", error=ValueError("bad"), hint="fix it")

    assert set(ok) == {"status", "feature", "stage", "warnings", "answer"} and ok["warnings"] == []
    assert failed.status_code == 422
    assert set(json.loads(failed.body)) == {"status", "stage", "detail", "error", "hint", "warnings"}
    assert json.loads(failed.body)["error"] == {"type": "ValueError", "message": "bad"}


def test_the_session_resource_is_unchanged_and_the_answer_uses_the_success_envelope():
    body = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", _pdf(), "application/pdf")}).json()

    session = client.get(f"/api/session/{body['session_id']}").json()
    answer = client.post(f"/api/session/{body['session_id']}/question", json={"question": "What is softmax?"}).json()

    assert session["status"] == "active" and "stage" not in session  # a session resource, not a workflow result
    assert {"question", "responses", "recommendations"} <= set(answer)  # backward compatible: keys stay top level
    assert (answer["status"], answer["feature"], answer["stage"], answer["warnings"]) == (
        "success", "Interactive Learning", "answered", [])
    assert json_violations(answer) == []
