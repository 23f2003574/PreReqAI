"""The web page asks the tutor and runs the interactive quiz through the existing session endpoints: what it calls, what it reads back, what a reload restores."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def test_the_page_has_the_tutor_and_quiz_controls_and_calls_the_existing_endpoints():
    for fragment in ('id="askForm"', 'id="question"', 'id="answers"', 'id="quizConcept"', 'id="quizNext"', 'id="quizCard"', 'id="mastery"',
                     '"/question"', '"/quiz/"', '"question"', '"reveal"', '"outcome"', "supporting_sections", "supporting_concepts", "suggested_followups",
                     "No tutoring model is configured", "if (state.tutorBusy) return;", "if (state.quizBusy) return;", "quiz_progress", "conversation_history"):
        assert fragment in PAGE, fragment
    assert "innerHTML" not in PAGE and "eval(" not in PAGE


def test_an_answer_carries_the_evidence_and_the_disclosure_the_page_shows(sid):
    body = client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"}).json()
    answer = body["responses"][0]
    assert body["status"] == "success" and answer["answer"].startswith("Attention:")
    assert answer["supporting_concepts"] == ["Attention"] and answer["supporting_sections"] and answer["suggested_followups"]
    assert any("No tutoring model is configured" in w for w in body["warnings"])


def test_a_question_the_tutor_cannot_answer_is_disclosed(sid):
    body = client.post(f"/api/session/{sid}/question", json={"question": "Explain residual streams"}).json()
    assert "not in PreReqAI's built-in concept registry" in body["responses"][0]["answer"]
    assert any("No tutoring model is configured" in w and "placeholder" in w for w in body["warnings"])


def test_invalid_questions_have_the_detail_and_hint_the_page_shows(sid):
    empty = client.post(f"/api/session/{sid}/question", json={"question": "  "})
    assert empty.status_code == 422 and empty.json()["detail"] and empty.json()["hint"]
    long = client.post(f"/api/session/{sid}/question", json={"question": "x" * 2001})
    assert long.status_code == 422 and "too long" in long.json()["detail"]
    assert client.post("/api/session/nope/question", json={"question": "hi"}).status_code == 404


def test_the_quiz_flow_the_page_runs_updates_mastery_and_survives_a_reload(sid):
    concepts = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", Path(SAMPLE).read_bytes(), "application/pdf")}).json()["report"]["concepts"]
    assert all(isinstance(name, str) for name in concepts)  # the page fills its concept selector from these
    question = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Softmax"}).json()
    assert {"question_id", "concept", "difficulty", "question"} <= set(question) and "answer" not in question
    revealed = client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": question["question_id"]}).json()
    assert revealed["answer"]
    done = client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": question["question_id"], "outcome": "knew"}).json()
    assert done["progress"]["concepts"][0] == {"concept": "Softmax", "attempts": 1, "knew": 1, "missed": 0, "mastery": 1.0, "status": "progressing"}
    session_manager.sessions.clear()  # a reload after a server restart
    restored = client.get(f"/api/session/{sid}").json()
    assert restored["quiz_progress"] == done["progress"]


def test_the_conversation_is_restored_from_the_session_history(sid):
    client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"})
    session_manager.sessions.clear()
    history = client.get(f"/api/session/{sid}").json()["conversation_history"]
    asked = {e["data"]["question_id"]: e["data"]["question"] for e in history if e["type"] == "question"}
    answers = [e["data"] for e in history if e["type"] == "answer"]
    assert [asked[a["question_id"]] for a in answers] == ["What is attention?"] and answers[0]["answers"][0].startswith("Attention:") and answers[0]["supporting_concepts"] == ["Attention"]


def test_quiz_failures_have_the_detail_and_hint_the_page_shows(sid):
    unsupported = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Quantum Gravity"})
    assert unsupported.status_code == 422 and unsupported.json()["detail"] and unsupported.json()["hint"]
    assert client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": "Softmax:1"}).status_code == 409
    assert client.get("/api/session/nope/quiz/question").status_code == 404
