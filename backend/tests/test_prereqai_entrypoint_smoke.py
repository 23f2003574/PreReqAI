"""End-to-end smoke for PreReqAI's supported entrypoint: the HTTP application.
A real (tiny) PDF is uploaded to POST /api/prerequisites/analyze, which runs the
platform's analysis pipeline; the returned session is then read and asked a
question through the platform's learning pipeline. Nothing is mocked and no
network is used."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import prerequisite_routes, session_routes
from backend.main import app
from backend.main import platform as main_platform
from backend.platform import platform

client = TestClient(app)


SAMPLE_PAPER = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"


def _paper_pdf() -> bytes:
    """The README quickstart's committed sample paper, so this smoke and the
    documented first run exercise the same input."""
    return SAMPLE_PAPER.read_bytes()


def test_the_application_and_its_routers_share_the_platform_pipelines():
    assert main_platform is platform
    assert prerequisite_routes.pipeline is platform.analysis
    assert session_routes.pipeline is platform.learning


def test_uploaded_paper_flows_through_analysis_session_and_tutoring():
    analysed = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", _paper_pdf(), "application/pdf")})

    assert analysed.status_code == 200
    body = analysed.json()
    assert body["status"] == "success" and body["feature"] == "Prerequisite Explorer"
    assert {"paper", "concepts", "prerequisites", "learning_plan", "readiness"} <= set(body["report"])

    session = client.get(f"/api/session/{body['session_id']}")
    assert session.status_code == 200
    assert session.json()["session_id"] == body["session_id"] and session.json()["status"] == "active"

    answer = client.post(f"/api/session/{body['session_id']}/question", json={"question": "What is softmax?"})
    assert answer.status_code == 200 and {"question", "responses", "recommendations"} <= set(answer.json())
    responses = answer.json()["responses"]
    assert responses and all(isinstance(r["answer"], str) and r["answer"] for r in responses)
    assert any("Softmax" in r["supporting_concepts"] for r in responses)  # grounded in the uploaded paper

    history = client.get(f"/api/session/{body['session_id']}").json()["conversation_history"]
    assert [entry["data"]["question"] for entry in history if entry["type"] == "question"] == ["What is softmax?"]


def test_invalid_input_and_unknown_sessions_fail_cleanly():
    bad = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", b"not a pdf", "application/pdf")})

    assert bad.status_code == 400 and bad.json()["detail"].startswith("Failed to process the uploaded paper")
    missing = client.get("/api/session/does-not-exist")
    assert missing.status_code == 404 and missing.json()["stage"] == "session_lookup" and missing.json()["hint"]
    assert client.post("/api/session/does-not-exist/question", json={"question": "x"}).status_code == 404


def test_sample_paper_analysis_result_through_the_http_entrypoint():
    """The documented first run must keep producing the same learner-facing answer."""
    response = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", _paper_pdf(), "application/pdf")})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success" and body["warnings"] == []
    report = body["report"]

    assert report["paper"]["title"] == "Attention Is All You Need (PreReqAI sample paper)"
    assert report["concepts"] == ["Transformer", "Attention", "Softmax"]
    status = {item["concept"]: item["satisfied"] for item in report["missing_prerequisites"]}
    assert status == {"Attention": True, "Neural Networks": False, "Linear Algebra": False, "Probability": False}
    assert [(step["concept"], step["estimated_hours"]) for step in report["learning_plan"]] == [
        ("Linear Algebra", 12), ("Probability", 10), ("Neural Networks", 15)]
    assert report["study_time"]["total_hours"] == 37
    assert report["readiness"]["ready_to_read"] is False and report["readiness"]["total_concepts"] == 3
