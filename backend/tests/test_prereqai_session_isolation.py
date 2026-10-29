"""Two sessions of the same paper are independent: studying, dropping a concept or asking a topic question in one
changes nothing in the other (a shared report or paper object would leak progress between learners)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"


def _analyze(client):
    with SAMPLE.open("rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]


def _state(client, sid):
    body = client.get(f"/api/session/{sid}").json()
    return body["readiness"], body["study_progress"], body["study_time"], client.get(f"/api/session/{sid}/plan").text


def test_progress_in_one_session_does_not_reach_another_session_of_the_same_paper():
    client = TestClient(app)
    first, second = _analyze(client), _analyze(client)
    untouched = _state(client, second)

    assert client.post(f"/api/prerequisites/sessions/{first}/studied", params={"concept": "Calculus"}).status_code == 200
    assert client.post(f"/api/prerequisites/sessions/{first}/known", params={"concept": "Probability"}).status_code == 200
    assert client.post(f"/api/session/{first}/question", json={"question": "Quiz me", "topic": "Softmax"}).status_code == 200

    changed = _state(client, first)
    assert changed[0]["completed_concepts"] == 1 and "Already known: Probability" in changed[3]
    assert _state(client, second) == untouched
    assert untouched[0]["completed_concepts"] == 0 and "Already known" not in untouched[3]


def test_a_question_topic_in_one_session_does_not_scope_another_sessions_quiz():
    client = TestClient(app)
    first, second = _analyze(client), _analyze(client)
    client.post(f"/api/session/{first}/question", json={"question": "Hello", "topic": "Softmax"})

    answer = client.post(f"/api/session/{second}/question", json={"question": "Quiz me"}).json()["responses"][0]["answer"]
    assert "Attention Q1" in answer and "Transformer Q1" in answer


def test_deleting_one_session_leaves_the_other_usable():
    client = TestClient(app)
    first, second = _analyze(client), _analyze(client)
    assert client.delete(f"/api/session/{first}").status_code == 200
    assert client.get(f"/api/session/{first}").status_code == 404
    assert client.get(f"/api/session/{second}").status_code == 200
