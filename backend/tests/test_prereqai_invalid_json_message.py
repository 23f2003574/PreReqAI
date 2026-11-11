from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
JSON = {"content-type": "application/json"}


def _question_url():
    from pathlib import Path
    sample = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
    with sample.open("rb") as handle:
        session_id = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    return f"/api/session/{session_id}/question"


def test_a_malformed_json_body_names_the_body_and_the_position():
    response = client.post(_question_url(), content="{bad", headers=JSON)
    body = response.json()
    assert response.status_code == 422 and body["status"] == "failure" and body["stage"] == "input"
    assert body["detail"] == "Invalid request: request body: JSON decode error (at character 1)"


def test_other_validation_messages_are_unchanged():
    url = _question_url()
    assert "question: Input should be a valid string" in client.post(url, json={"question": 5}).json()["detail"]
    assert client.post(url, json={"question": ""}).status_code == 422
