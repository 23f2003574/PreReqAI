"""A 404 for an unknown session explains the likely cause: sessions vanish on restart unless PREREQAI_SESSION_DIR is set."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai
UNKNOWN = "/api/session/00000000-0000-0000-0000-000000000000"


def test_without_a_session_dir_the_hint_says_sessions_do_not_survive_a_restart(monkeypatch):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    response = TestClient(app).get(UNKNOWN)
    assert response.status_code == 404
    hint = response.json()["hint"]
    assert hint.startswith("Run an analysis first and use the session_id it returns.")
    assert "lost when the server restarts" in hint and "PREREQAI_SESSION_DIR" in hint


def test_with_a_session_dir_the_hint_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    response = TestClient(app).get(UNKNOWN)
    assert response.status_code == 404
    assert response.json()["hint"] == "Run an analysis first and use the session_id it returns."
