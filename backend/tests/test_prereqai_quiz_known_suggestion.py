"""Quiz results can suggest marking a prerequisite subject as known; the learner decides, and nothing else changes."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor import quiz_session
from backend.tutor.quiz_bank import SUBJECT_QUIZ_BANK

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)
SUBJECT = "Probability"  # a planned prerequisite of the sample paper with three subject questions


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def answer(sid, outcome, concept=SUBJECT):
    question = client.get(f"/api/session/{sid}/quiz/question", params={"concept": concept}).json()["question_id"]
    return client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": question, "outcome": outcome}).json()


def test_the_thresholds_are_conservative_and_documented():
    assert quiz_session.SUGGEST_MIN_ATTEMPTS >= 3 and quiz_session.SUGGEST_MIN_SHARE >= 0.75 and quiz_session.SUGGEST_MIN_DISTINCT >= 2
    assert quiz_session.MASTERY_STREAK >= 2 and len(SUBJECT_QUIZ_BANK[SUBJECT]) >= quiz_session.SUGGEST_MIN_DISTINCT
    assert "suggest" in quiz_session.__doc__ or "self-graded" in open(quiz_session.__file__, encoding="utf-8").read()


def test_a_single_lucky_answer_or_two_correct_ones_suggest_nothing(sid):
    assert answer(sid, "knew")["suggest_known"] == []
    assert answer(sid, "knew")["suggest_known"] == []  # the "mastered" streak is reached, but there are too few answers


def test_mixed_results_or_one_repeated_question_suggest_nothing(sid):
    for outcome in ("missed", "knew", "knew"):
        body = answer(sid, outcome)
    assert body["suggest_known"] == [] and body["progress"]["concepts"][0]["status"] == "mastered"  # 2 of 3: below the share
    question = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Calculus"}).json()["question_id"]
    session = session_manager.get(sid)  # three "knew" on one question: a streak and a share, but not different questions
    session.quiz_attempts.extend({"question_id": question, "concept": "Calculus", "outcome": "knew", "revealed": False} for _ in range(3))
    assert [s["concept"] for s in quiz_session.known_suggestions(session)] == []


def test_enough_varied_correct_answers_give_a_structured_suggestion_and_change_nothing_else(sid):
    before_plan = client.get(f"/api/session/{sid}").json()["study_progress"]
    for _ in range(2):
        answer(sid, "knew")
    body = answer(sid, "knew")
    [suggestion] = body["suggest_known"]
    assert suggestion["concept"] == SUBJECT and suggestion["attempts"] == 3 and suggestion["knew"] == 3 and suggestion["mastery"] == 1.0
    assert suggestion["distinct_questions"] == 3 and SUBJECT in suggestion["reason"] and "3 of your 3" in suggestion["reason"]
    assert body["progress"]["concepts"] == [{"concept": SUBJECT, "attempts": 3, "knew": 3, "missed": 0, "mastery": 1.0, "status": "mastered"}]  # scoring unchanged
    after = client.get(f"/api/session/{sid}").json()
    assert after["study_progress"] == before_plan and SUBJECT in [s["concept"] for s in after["study_progress"]]  # never marked automatically
    assert after["suggest_known"] == body["suggest_known"] == client.get(f"/api/session/{sid}/quiz/progress").json()["suggest_known"]  # one entry, however read


def test_accepting_uses_the_existing_endpoint_and_the_subject_is_not_suggested_again(sid):
    for _ in range(3):
        answer(sid, "knew")
    accepted = client.post(f"/api/prerequisites/sessions/{sid}/known", params={"concept": SUBJECT}).json()
    assert accepted["status"] == "success" and SUBJECT not in [s["concept"] for s in accepted["report"]["learning_plan"]]
    assert client.get(f"/api/session/{sid}/quiz/progress").json()["suggest_known"] == []  # known: not suggested again
    assert answer(sid, "knew")["suggest_known"] == []  # and quizzing it further does not bring it back
    assert client.get(f"/api/session/{sid}/quiz/progress").json()["progress"]["concepts"][0]["attempts"] == 4  # scores kept counting


def test_ignoring_a_suggestion_leaves_progress_unchanged_and_studied_subjects_are_not_suggested(sid):
    for _ in range(3):
        answer(sid, "knew")
    first = client.get(f"/api/session/{sid}").json()
    again = client.get(f"/api/session/{sid}").json()
    assert first["suggest_known"] and first["study_progress"] == again["study_progress"] and first["readiness"] == again["readiness"]
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": SUBJECT})
    assert client.get(f"/api/session/{sid}").json()["suggest_known"] == []  # studied: nothing left to suggest


def test_a_concept_outside_the_plan_and_a_paper_without_a_session_paper_are_never_suggested(sid):
    for _ in range(3):
        answer(sid, "knew", "Softmax")  # a registry concept, not a planned prerequisite
    session = session_manager.get(sid)
    assert quiz_session.known_suggestions(session) == []
    session.paper = None
    assert quiz_session.known_suggestions(session) == []


def test_the_page_shows_the_suggestion_and_offers_an_explicit_choice_through_the_known_endpoint():
    for fragment in ('id="suggest"', "function renderSuggestions()", "function acceptSuggestion(concept)", "state.suggestions = body.suggest_known || []",
                     "Suggestion: you may already know ", "s.reason", '"Mark " + s.concept + " as known"', '"Not now"', "state.dismissed[s.concept] = true",
                     "await setKnown(concept, true);  // the existing known endpoint", "return act(", "state.known.indexOf(concept) >= 0"):
        assert fragment in PAGE, fragment
    assert "setKnown(s.concept" not in PAGE.split("function renderSuggestions()")[1].split("function acceptSuggestion")[0]  # rendering alone never marks anything
    assert PAGE.count('"/known"') == 1 and "innerHTML" not in PAGE  # the one existing known endpoint, no new calls or HTML injection
