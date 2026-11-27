"""Every quiz question, about paper concepts and about prerequisite subjects, has an explanation that is shown once its answer is revealed, in the interactive quiz and the tutor's quiz."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.tutor.quiz_bank import QUIZ_BANK, QUIZ_EXPLANATIONS, SUBJECT_QUIZ_BANK, unexplained_questions
from backend.tutor.quiz_explanations_remaining import CONCEPT_ROWS, SUBJECT_ROWS

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


def test_every_question_in_both_banks_has_an_explanation():
    assert unexplained_questions() == []
    assert sum(len(v) for v in QUIZ_BANK.values()) == 270 and sum(len(v) for v in SUBJECT_QUIZ_BANK.values()) == 27


def test_explanations_explain_and_do_not_repeat_the_answer():
    for bank in (QUIZ_BANK, SUBJECT_QUIZ_BANK):
        for name, items in bank.items():
            for item in items:
                explanation = QUIZ_EXPLANATIONS[(name, item["question"])]
                assert len(explanation) >= 20 and explanation.strip() == explanation, (name, item["question"])
                assert " ".join(explanation.lower().split()) != " ".join(item["answer"].lower().split()), (name, item["question"])


def test_the_remaining_rows_cover_119_questions_exactly_once():
    assert len(CONCEPT_ROWS) == 92 and len(SUBJECT_ROWS) == 27
    keys = [(name, phrase) for name, phrase, _ in [*CONCEPT_ROWS, *SUBJECT_ROWS]]
    assert len(set(keys)) == len(keys)


def test_a_bank_question_without_an_explanation_would_be_reported():
    QUIZ_BANK["Softmax"].append({"question": "A question nobody explained?", "answer": "No.", "difficulty": "Easy"})
    try:
        assert unexplained_questions() == [("Softmax", "A question nobody explained?")]
    finally:
        QUIZ_BANK["Softmax"].pop()


def _session():
    client = TestClient(app)
    with open(SAMPLE, "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    return client, f"/api/session/{sid}"


def test_the_interactive_quiz_reveals_an_explanation_for_a_paper_concept_and_for_a_subject():
    client, base = _session()
    served = []
    for params in ({"concept": "Softmax"}, {"concept": "Linear Algebra"}):
        question = client.get(f"{base}/quiz/question", params=params).json()
        served.append(question)
        revealed = client.post(f"{base}/quiz/reveal", json={"question_id": question["question_id"]}).json()
        assert revealed["explanation"] == QUIZ_EXPLANATIONS[(params["concept"], question["question"])], (params, revealed)
    assert len({q["concept"] for q in served}) == 2


def test_the_tutor_quiz_shows_the_explanation_with_the_answer():
    from types import SimpleNamespace

    from backend.tutor.rule_based_tutor import RuleBasedTutor

    reply = RuleBasedTutor._quiz_answer(SimpleNamespace(concepts=[]), SimpleNamespace(active_concept=None), "Quiz me on Softmax")
    for item in QUIZ_BANK["Softmax"]:
        assert f"Answer: {item['answer']} Why: {QUIZ_EXPLANATIONS[('Softmax', item['question'])]}" in reply
    subject = RuleBasedTutor._quiz_answer(SimpleNamespace(concepts=[]), SimpleNamespace(active_concept=None), "Quiz me on Attention")
    assert subject.count("Why:") == len(QUIZ_BANK["Attention"])
