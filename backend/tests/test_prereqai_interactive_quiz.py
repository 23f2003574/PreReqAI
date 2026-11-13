"""The interactive quiz: a question without its answer, a reveal, a recorded outcome, and per-concept mastery that survives a reload."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor.quiz_bank import QUIZ_BANK

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def ask(sid, concept=None):
    return client.get(f"/api/session/{sid}/quiz/question", params={"concept": concept} if concept else {})


def post(sid, op, **body):
    return client.post(f"/api/session/{sid}/quiz/{op}", json=body)


def answer_once(sid, outcome, concept=None):
    question = ask(sid, concept).json()
    assert post(sid, "reveal", question_id=question["question_id"]).status_code == 200
    return question, post(sid, "outcome", question_id=question["question_id"], outcome=outcome)


def test_the_question_never_contains_the_answer(sid):
    body = ask(sid, "Softmax").json()
    assert body["status"] == "success" and body["concept"] == "Softmax" and body["question"] == QUIZ_BANK["Softmax"][0]["question"]
    assert set(body) >= {"question_id", "difficulty"} and QUIZ_BANK["Softmax"][0]["answer"] not in str(body) and "answer" not in body


def test_reveal_returns_the_answer_and_the_full_workflow_updates_mastery(sid):
    question = ask(sid, "Softmax").json()
    assert post(sid, "reveal", question_id=question["question_id"]).json()["answer"] == QUIZ_BANK["Softmax"][0]["answer"]
    done = post(sid, "outcome", question_id=question["question_id"], outcome="knew").json()
    assert done["progress"]["concepts"] == [{"concept": "Softmax", "attempts": 1, "knew": 1, "missed": 0, "mastery": 1.0, "status": "progressing"}]
    assert client.get(f"/api/session/{sid}").json()["quiz_progress"] == done["progress"]
    assert client.get(f"/api/session/{sid}/quiz/progress").json()["progress"] == done["progress"]


def test_progress_survives_a_reload_and_the_report_keeps_it(sid):
    answer_once(sid, "missed", "Softmax")
    answer_once(sid, "knew", "Softmax")
    session_manager.sessions.clear()  # a restart: only the saved file remains
    reloaded = client.get(f"/api/session/{sid}").json()["quiz_progress"]
    assert reloaded["attempts"] == 2 and reloaded["concepts"][0]["mastery"] == 0.5 and reloaded["concepts"][0]["status"] == "progressing"
    assert session_manager.get(sid).report["quiz_progress"] == reloaded


def test_mastery_needs_a_streak_and_a_miss_resets_it(sid):
    statuses = [answer_once(sid, outcome, "Dropout")[1].json()["progress"]["concepts"][0]["status"] for outcome in ("knew", "knew", "missed")]
    assert statuses == ["progressing", "mastered", "needs_practice"]


def test_without_a_concept_the_least_practised_paper_concept_comes_first(sid):
    paper_concepts = sorted(c.name for c in session_manager.get(sid).paper.concepts if c.name in QUIZ_BANK)
    first = ask(sid).json()
    assert first["concept"] == paper_concepts[0]  # nothing attempted yet: the first by name
    answer_once(sid, "knew")
    assert ask(sid).json()["concept"] == paper_concepts[1]  # another concept now has fewer attempts


def test_the_same_concept_rotates_through_its_questions(sid):
    ids = []
    for _ in range(len(QUIZ_BANK["Attention"]) + 1):
        question, _ = answer_once(sid, "knew", "Attention")
        ids.append(question["question_id"])
    assert ids[:len(QUIZ_BANK["Attention"])] == [f"Attention:{n}" for n in range(1, len(QUIZ_BANK["Attention"]) + 1)] and ids[-1] == "Attention:1"


def test_repeated_submissions_are_counted_once(sid):
    question, first = answer_once(sid, "knew", "Softmax")
    again = post(sid, "outcome", question_id=question["question_id"], outcome="knew")
    assert first.status_code == 200 and again.status_code == 409 and again.json()["hint"]
    assert client.get(f"/api/session/{sid}/quiz/progress").json()["progress"]["attempts"] == 1
    assert post(sid, "reveal", question_id=question["question_id"]).status_code == 409  # no longer pending


def test_invalid_requests_are_refused_without_changing_anything(sid):
    served = ask(sid, "Softmax").json()["question_id"]
    assert ask(sid, "Quantum Gravity").status_code == 422 and ask(sid, "Calculus").status_code == 422
    assert post(sid, "reveal", question_id="Softmax:99").status_code == 404 and post(sid, "reveal", question_id="nonsense").status_code == 404
    assert post(sid, "reveal", question_id="Dropout:1").status_code == 409  # valid id that was never served
    assert post(sid, "outcome", question_id=served, outcome="maybe").status_code == 422
    assert post(sid, "outcome", question_id="Dropout:1", outcome="knew").status_code == 409
    assert post(sid, "outcome", outcome="knew").status_code == 422 and client.get("/api/session/nope/quiz/question").status_code == 404
    assert client.get(f"/api/session/{sid}/quiz/progress").json()["progress"] == {"attempts": 0, "concepts": []}
    assert post(sid, "outcome", question_id=served, outcome="missed").status_code == 200  # the served question is still answerable


def test_concept_names_are_matched_loosely(sid):
    assert ask(sid, "self-attention").json()["concept"] == "Self-Attention" and ask(sid, "  SOFTMAX ").json()["concept"] == "Softmax"


def test_the_text_quiz_is_unchanged(sid):
    answer = client.post(f"/api/session/{sid}/question", json={"question": "Quiz me on Softmax"}).json()["responses"][0]["answer"]
    assert answer.startswith("Softmax Q1 (") and "Answer: " + QUIZ_BANK["Softmax"][0]["answer"] in answer


def test_a_session_saved_before_the_quiz_existed_still_quizzes(sid, tmp_path):
    import pickle

    path = tmp_path / f"{sid}.session"
    session = pickle.loads(path.read_bytes())
    session.schema_version = 2
    del session.__dict__["quiz_attempts"], session.__dict__["quiz_pending"]
    path.write_bytes(pickle.dumps(session))
    session_manager.sessions.clear()
    assert answer_once(sid, "knew", "Softmax")[1].status_code == 200
