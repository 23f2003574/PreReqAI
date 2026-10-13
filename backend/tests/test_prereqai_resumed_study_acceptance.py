"""Acceptance: a learner uploads a paper, studies, asks what is left, restarts the server and finishes the plan."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


def _ask(sid, question):
    response = client.post(f"/api/session/{sid}/question", json={"question": question})
    assert response.status_code == 200
    return response.json()["responses"][0]["answer"]


def _studied(sid, concept, method="post"):
    return getattr(client, method)(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": concept})


def test_a_learner_works_through_the_plan_across_a_server_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    session_manager.sessions.clear()
    upload = client.post("/api/prerequisites/analyze", data={"known": "Calculus", "studied": "Linear Algebra"},
                         files={"paper": ("p.pdf", SAMPLE.read_bytes(), "application/pdf")}).json()
    sid = upload["session_id"]
    assert upload["report"]["readiness"]["completed_concepts"] == 1

    answer = _ask(sid, "What should I learn first?")
    assert "Calculus" not in answer and "Probability" in answer and "Already studied: Linear Algebra" in answer

    # A mistaken concept is refused and changes nothing the learner sees.
    assert _studied(sid, "Quantum Gravity").status_code == 422
    assert _ask(sid, "What should I learn first?") == answer

    assert _studied(sid, "probability").status_code == 200
    session_manager.sessions.clear()  # the server restarts: only the saved session remains

    restored = client.get(f"/api/session/{sid}").json()
    assert restored["readiness"]["completed_concepts"] == 2
    answer = _ask(sid, "What should I learn first?")
    assert "Probability" not in answer.split("Already studied")[0] and "Neural Networks" in answer
    assert "Study Probability" not in [a["title"] for a in session_manager.get(sid).report["study_actions"]]

    assert _studied(sid, "Neural Networks").status_code == 200
    assert "ready to read the paper" in _ask(sid, "What should I learn first?")
    assert client.get(f"/api/session/{sid}").json()["readiness"]["ready_to_read"] is True

    assert _studied(sid, "Neural Networks", "delete").status_code == 200  # a slip is undone
    assert "Neural Networks" in _ask(sid, "What should I learn first?")

    assert client.delete(f"/api/session/{sid}").status_code == 200
    assert client.get(f"/api/session/{sid}").status_code == 404
    assert not list((tmp_path / "sessions").glob("*.session"))
