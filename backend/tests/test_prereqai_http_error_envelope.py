"""Unknown paths and wrong methods answer with the same failure envelope as every other PreReqAI error."""
from starlette.testclient import TestClient

from backend.main import app

KEYS = {"status", "stage", "detail", "error", "hint", "warnings"}


def test_unknown_path_has_the_failure_envelope():
    response = TestClient(app).get("/api/nothing")
    body = response.json()
    assert response.status_code == 404
    assert set(body) == KEYS and body["status"] == "failure" and body["detail"] == "Not Found"


def test_wrong_method_has_the_envelope_and_keeps_the_allow_header():
    response = TestClient(app).get("/api/prerequisites/analyze")
    body = response.json()
    assert response.status_code == 405
    assert set(body) == KEYS and body["status"] == "failure" and body["detail"] == "Method Not Allowed"
    assert "POST" in response.headers["allow"]


def test_existing_envelopes_are_unchanged():
    body = TestClient(app).get("/api/session/nope").json()
    assert body["stage"] == "session_lookup" and set(body) == KEYS
