"""End-to-end smoke for PreReqAI's supported entrypoint: the HTTP application.
A real (tiny) PDF is uploaded to POST /api/prerequisites/analyze, which runs the
platform's analysis pipeline; the returned session is then read and asked a
question through the platform's learning pipeline. Nothing is mocked and no
network is used."""
import fitz
from fastapi.testclient import TestClient

from backend.api import prerequisite_routes, session_routes
from backend.main import app
from backend.main import platform as main_platform
from backend.platform import platform

client = TestClient(app)


def _paper_pdf() -> bytes:
    document = fitz.open()
    document.new_page().insert_text(
        (72, 72),
        "Attention Is All You Need\n\nAbstract\nWe propose the Transformer, a model based on attention.\n\n"
        "1 Introduction\nRecurrent networks are slow. We use self-attention and softmax.\n\n"
        "2 Method\nThe loss is L = sum_i (y_i - f(x_i))^2 and we train with gradient descent.\n",
        fontsize=11,
    )
    return document.tobytes()


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


def test_invalid_input_and_unknown_sessions_fail_cleanly():
    bad = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", b"not a pdf", "application/pdf")})

    assert bad.status_code == 400 and bad.json()["detail"].startswith("Failed to process the uploaded paper")
    assert client.get("/api/session/does-not-exist").status_code == 404
    assert client.post("/api/session/does-not-exist/question", json={"question": "x"}).status_code == 404
