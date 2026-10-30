"""The README's HTTP API table states what the endpoints really accept and refuse (checked against the running app)."""
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text()
client = TestClient(app)
PDF = (ROOT / "examples/prerequisites/sample-paper.pdf").read_bytes()
ANALYZE = "/api/prerequisites/analyze"


def _session():
    return client.post(ANALYZE, files={"paper": ("p.pdf", io.BytesIO(PDF), "application/pdf")}).json()["session_id"]


def test_analyze_row_lists_the_422_cases_the_endpoint_really_returns():
    row = next(line for line in README.splitlines() if line.startswith("| `POST /api/prerequisites/analyze`"))
    assert "`source`" in row and "neither or both" in row and "oversized" in row and "`resume`" in row
    assert client.post(ANALYZE).status_code == 422  # neither
    assert client.post(ANALYZE, files={"paper": ("p.pdf", io.BytesIO(PDF), "application/pdf")}, data={"source": "1706.03762"}).status_code == 422  # both
    assert client.post(ANALYZE, data={"source": "not a paper"}).status_code == 422
    assert client.post(ANALYZE, files={"paper": ("p.pdf", io.BytesIO(PDF), "application/pdf")}, data={"known": "a" * 201}).status_code == 422
    assert client.post(ANALYZE, files={"paper": ("p.pdf", io.BytesIO(PDF), "application/pdf"), "resume": ("r.md", b"hello")}).status_code == 422


def test_question_row_says_a_study_plan_concept_is_a_valid_topic_and_an_unknown_one_is_a_422():
    row = next(line for line in README.splitlines() if line.startswith("| `POST /api/session/{session_id}/question`"))
    assert "nor a concept in its study plan" in row
    sid = _session()
    assert client.post(f"/api/session/{sid}/question", json={"question": "Quiz me", "topic": "Probability"}).status_code == 200
    assert client.post(f"/api/session/{sid}/question", json={"question": "Quiz me", "topic": "Cooking"}).status_code == 422


def test_sessions_are_not_claimed_to_always_end_with_the_server():
    assert "end with the server process unless `PREREQAI_SESSION_DIR` is set" in README
