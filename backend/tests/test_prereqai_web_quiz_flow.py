"""The learner's quiz workflow end to end: topics the server can quiz, the position of a question, a full round, continuing a pending question after a
reload, and the tutor's error states, through the API the page calls and the page's own wiring."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor.quiz_bank import QUIZ_BANK, SUBJECT_QUIZ_BANK

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.delenv("PREREQAI_TUTOR_PROVIDER", raising=False)
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def question(sid, concept=None):
    return client.get(f"/api/session/{sid}/quiz/question", params={"concept": concept} if concept else {})


def outcome(sid, identifier, result="knew"):
    return client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": identifier, "outcome": result}).json()


def test_the_session_lists_only_topics_the_quiz_can_serve_paper_concepts_and_plan_prerequisites(sid):
    topics = client.get(f"/api/session/{sid}").json()["quiz_topics"]
    kinds = {t["concept"]: t["kind"] for t in topics}
    assert {"Softmax", "Attention"} <= {t["concept"] for t in topics if t["kind"] == "paper"} and kinds["Probability"] == "prerequisite" and kinds["Calculus"] == "prerequisite"
    assert len(kinds) == len(topics) and all(t["questions"] >= 1 for t in topics)  # one entry per name, none without questions
    assert all(question(sid, t["concept"]).status_code == 200 for t in topics)  # every offered topic really is served
    assert {t["concept"] for t in topics if t["kind"] == "paper"} <= set(QUIZ_BANK) and {"Probability", "Calculus"} <= set(SUBJECT_QUIZ_BANK)
    assert question(sid, "Astrology").status_code == 422 and question(sid, "Gravity").json()["status"] == "failure"  # unsupported: refused as before


def test_a_question_says_which_of_the_topics_questions_it_is_and_a_full_round_reaches_its_end(sid):
    seen, last = [], None
    for _ in range(3):
        served = question(sid, "Calculus").json()
        assert served["of"] == 3 and served["number"] in (1, 2, 3) and "answer" not in served
        seen.append(served["question_id"])
        last = outcome(sid, served["question_id"], "knew")
    assert sorted(seen) == ["Calculus:1", "Calculus:2", "Calculus:3"]  # a round visits every question once, in a stable order
    assert last["progress"]["concepts"] == [{"concept": "Calculus", "attempts": 3, "knew": 3, "missed": 0, "mastery": 1.0, "status": "mastered"}]
    assert [s["concept"] for s in last["suggest_known"]] == ["Calculus"] and "Calculus" in [t["concept"] for t in last["topics"]]  # offered, never applied
    assert "Calculus" in [s["concept"] for s in client.get(f"/api/session/{sid}").json()["study_progress"]]


def test_a_served_question_survives_a_reload_without_its_answer_and_is_gone_once_answered(sid):
    served = question(sid, "Probability").json()
    client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": served["question_id"]})
    session_manager.sessions.clear()  # a reload after a restart
    [pending] = client.get(f"/api/session/{sid}").json()["quiz_pending"]
    assert pending == {"question_id": served["question_id"], "concept": "Probability", "difficulty": served["difficulty"], "question": served["question"], "revealed": True}
    assert "answer" not in pending
    again = client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": served["question_id"]}).json()  # the page fetches the answer again
    assert again["answer"] == SUBJECT_QUIZ_BANK["Probability"][int(served["question_id"].rpartition(":")[2]) - 1]["answer"]
    outcome(sid, served["question_id"], "missed")
    assert client.get(f"/api/session/{sid}").json()["quiz_pending"] == []
    assert question(sid, "Probability").json()["question_id"] != served["question_id"]  # and the next one rotates on


def test_topics_follow_the_plan_and_quiz_activity_never_changes_known_or_studied_state(sid):
    before = client.get(f"/api/session/{sid}").json()
    for concept in ("Probability", "Softmax"):
        outcome(sid, question(sid, concept).json()["question_id"], "knew")
    after = client.get(f"/api/session/{sid}").json()
    assert after["study_progress"] == before["study_progress"] and after["readiness"] == before["readiness"]  # quiz answers alone change no progress
    client.post(f"/api/prerequisites/sessions/{sid}/known", params={"concept": "Probability"})
    progress = client.get(f"/api/session/{sid}/quiz/progress").json()
    assert "Probability" not in [t["concept"] for t in progress["topics"] if t["kind"] == "prerequisite"]  # known: left the plan
    assert [c["concept"] for c in progress["progress"]["concepts"]] == ["Probability", "Softmax"]  # its attempts are kept


def test_the_tutor_answers_keep_the_conversation_and_failures_give_the_detail_and_hint_the_page_shows(sid):
    answered = client.post(f"/api/session/{sid}/question", json={"question": "What is attention?"}).json()
    assert answered["status"] == "success" and answered["responses"][0]["answer"].startswith("Attention") and answered["warnings"]
    assert len(client.get(f"/api/session/{sid}").json()["conversation_history"]) >= 1  # restored with the session
    for body in ({"question": "   "}, {"question": "x" * 5000}):
        refused = client.post(f"/api/session/{sid}/question", json=body)
        assert refused.status_code == 422 and refused.json()["detail"] and refused.json()["hint"]
    assert client.post("/api/session/00000000-0000-4000-8000-000000000000/question", json={"question": "hi"}).status_code == 404


def test_the_page_offers_the_servers_topics_runs_rounds_and_continues_a_pending_question():
    for fragment in ("async function loadQuizTopics()", 'quizUrl("progress")', "state.quizTopics = body.topics", "optgroup", "Concepts in this paper",
                     "Prerequisites in your study plan", "function renderRound()", '"Round complete on "', "answered in this round", "round.done[card.id]",
                     "state.round = { concept: body.concept, total: body.of", "function restoredCard(body)", "body.quiz_pending", "body.quiz_topics",
                     "if (state.card && state.card.revealed) reveal();", "Practise "):
        assert fragment in PAGE, fragment
    rendering = PAGE.split("function renderRound()")[1].split("function renderCard()")[0]
    assert "setKnown" not in rendering and "known" not in rendering.replace("you knew", "")  # a finished round never marks anything known
    assert "innerHTML" not in PAGE and PAGE.count('"/known"') == 1  # no new calls to the plan and no HTML injection
    assert "width=device-width" in PAGE and "@media (max-width: 520px)" in PAGE  # the existing responsive layout is kept
