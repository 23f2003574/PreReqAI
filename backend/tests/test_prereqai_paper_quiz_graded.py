"""Paper questions are graded by the server before anything is revealed, recorded as assessed evidence, and assessed once."""
import pytest

from backend.tutor import diagnostic, paper_quiz
from backend.tutor.quiz_session import QuizError

pytestmark = pytest.mark.prereqai


class Session:
    def __init__(self):
        self.quiz_attempts, self.quiz_pending, self.report = [], {}, {"concept_evidence": []}


QUESTION = {"question_id": "cloze~1", "concept": "Attention", "kind": "cloze", "answer": "attention", "aliases": [], "quotation": "Attention is all you need.", "page_number": 3, "section": "Method"}


@pytest.fixture
def session(monkeypatch):
    monkeypatch.setattr(paper_quiz, "find", lambda s, i: (1, QUESTION) if str(i) == "cloze~1" else (None, None))
    return Session()


def test_a_correct_answer_is_assessed_without_a_reveal_and_carries_the_quotation(session):
    verdict = paper_quiz.grade(session, "cloze~1", "Attention", "high")
    assert verdict["correct"] is True and verdict["quotation"] and verdict["page_number"] == 3
    attempt = session.quiz_attempts[-1]
    assert attempt["graded"] is True and attempt["correct"] is True and attempt["confidence"] == "high" and attempt["kind"] == "paper" and attempt["revealed"] is False
    assert diagnostic.assessed_summary(session)["Attention"] == {"graded": 1, "correct": 1, "high_confidence_wrong": 0}


def test_a_wrong_answer_is_recorded_as_missed_and_confident_misses_are_counted(session):
    assert paper_quiz.grade(session, "cloze~1", "zebra", "high")["correct"] is False
    assert session.quiz_attempts[-1]["outcome"] == "missed" and diagnostic.assessed_summary(session)["Attention"]["high_confidence_wrong"] == 1


def test_a_question_is_assessed_once(session):
    paper_quiz.grade(session, "cloze~1", "attention", "low")
    with pytest.raises(QuizError) as info:
        paper_quiz.grade(session, "cloze~1", "attention", "low")
    assert info.value.kind == "state" and len(session.quiz_attempts) == 1


def test_a_revealed_question_can_no_longer_become_assessed_evidence(session):
    session.quiz_pending["cloze~1"] = {"revealed": True}
    with pytest.raises(QuizError) as info:
        paper_quiz.grade(session, "cloze~1", "attention", "high")
    assert info.value.kind == "state" and session.quiz_attempts == []
    session.quiz_pending.clear()
    session.quiz_attempts.append({"question_id": "cloze~1", "concept": "Attention", "outcome": "knew", "revealed": True, "kind": "paper"})  # a self-reported one after a reveal
    with pytest.raises(QuizError):
        paper_quiz.grade(session, "cloze~1", "attention", "high")


@pytest.mark.parametrize("attempt,confidence,kind", [("", "low", "outcome"), ("x", "sure", "outcome")])
def test_bad_input_is_refused_and_records_nothing(session, attempt, confidence, kind):
    with pytest.raises(QuizError) as info:
        paper_quiz.grade(session, "cloze~1", attempt, confidence)
    assert info.value.kind == kind and session.quiz_attempts == []
    with pytest.raises(QuizError) as unknown:
        paper_quiz.grade(session, "nope", "x", "low")
    assert unknown.value.kind == "unknown"


def test_assessed_paper_answers_change_the_adaptive_plan(session):
    from backend import adaptive_plan

    for _ in range(3):
        session.quiz_attempts.append({"question_id": f"q{len(session.quiz_attempts)}", "concept": "Attention", "outcome": "missed", "graded": True, "correct": False, "confidence": "medium", "kind": "paper"})
    report = {"learning_plan": [{"step": 1, "concept": "Attention", "estimated_hours": 4.0}], "missing_prerequisites": [{"concept": "Attention", "importance": "essential"}], "study_progress": []}
    assert adaptive_plan.propose(report, session.quiz_attempts)["plan"][0]["hours"] == 6.0
