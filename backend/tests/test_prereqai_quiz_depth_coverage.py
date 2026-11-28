"""Every concept has at least two distinct quiz questions with real answers, so it can reach mastery, and the page shows the explanation after the answer is revealed."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.concepts.concept_registry import ConceptRegistry
from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.tutor.quiz_bank import QUIZ_BANK, QUIZ_EXPLANATIONS
from backend.tutor.quiz_bank_depth import ROWS
from backend.tutor.quiz_session import MASTERY_DISTINCT, SUGGEST_MIN_DISTINCT

pytestmark = pytest.mark.prereqai
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)
GENERIC = ("question 2", "another question", "placeholder", "lorem", "tbd", "todo")


def test_every_registered_concept_has_at_least_two_distinct_questions():
    names = {c.name for c in ConceptRegistry().all()}
    assert set(QUIZ_BANK) == names
    for name, items in QUIZ_BANK.items():
        questions = [item["question"].strip().lower() for item in items]
        assert len(items) >= max(MASTERY_DISTINCT, SUGGEST_MIN_DISTINCT) and len(set(questions)) == len(questions), name  # mastery needs different questions


def test_the_added_questions_are_real_ones_with_substantive_answers_and_explanations():
    assert len(ROWS) == 43 and len({r[0] for r in ROWS}) == 43
    for concept, question, answer, explanation, difficulty in ROWS:
        assert question.endswith("?") and len(question.split()) >= 6 and not any(g in question.lower() for g in GENERIC), question
        assert len(answer.split()) >= 8 and len(explanation.split()) >= 8 and difficulty in {"Easy", "Medium", "Hard"} and answer != explanation
        assert [i["question"] for i in QUIZ_BANK[concept]].count(question) == 1 and QUIZ_EXPLANATIONS[(concept, question)] == explanation
        assert len(QUIZ_BANK[concept]) >= 2 and QUIZ_BANK[concept][0]["question"] != question  # appended after the original, whose identifier does not change


def test_the_original_questions_keep_their_identifiers_and_text():
    assert QUIZ_BANK["Transformer"][0]["question"] == "Why are positional encodings required?" and QUIZ_BANK["Variational Autoencoder"][0]["question"].startswith("What does the KL term")


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.delenv("PREREQAI_PROFILE_DIR", raising=False)
    session_manager.sessions.clear()
    yield platform.analyze("examples/prerequisites/sample-paper.pdf")["session_id"]
    session_manager.sessions.clear()


def test_a_concept_that_had_one_question_can_now_be_mastered_through_the_quiz(sid):
    seen = []
    for _ in range(4):
        asked = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Residual Connection"}).json()
        seen.append(asked["question_id"])
        revealed = client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": asked["question_id"]}).json()
        assert revealed["answer"]
        body = client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": asked["question_id"], "outcome": "knew"}).json()
    assert len(set(seen)) == 3  # the three questions of the concept are served in turn
    assert body["progress"]["concepts"][0]["status"] == "mastered"  # four correct answers over different questions


def test_reveal_returns_the_explanation_of_an_added_question(sid):
    added = next(question for concept, question, *_ in ROWS if concept == "Adam Optimizer")
    explained = []
    for _ in range(2):
        asked = client.get(f"/api/session/{sid}/quiz/question", params={"concept": "Adam Optimizer"}).json()
        revealed = client.post(f"/api/session/{sid}/quiz/reveal", json={"question_id": asked["question_id"]}).json()
        if asked["question"] == added:
            explained.append(revealed["explanation"])
        client.post(f"/api/session/{sid}/quiz/outcome", json={"question_id": asked["question_id"], "outcome": "knew"})
    assert explained and len(explained[0].split()) >= 8  # the added question is served and its explanation comes with the answer


def test_the_page_shows_the_explanation_once_the_answer_is_revealed():
    assert "card.explanation = body.explanation" in PAGE and 'why.id = "quizExplanation"' in PAGE and "Why: " in PAGE
    shown = PAGE.index('card.appendChild(el("p", "Answer: " + c.answer));')
    assert shown < PAGE.index("c.explanation", shown) < PAGE.index("How did you do?")  # inside the revealed branch, before the self-grading buttons
