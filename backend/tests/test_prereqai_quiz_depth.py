"""Quiz depth: mastery needs two different questions, the concepts that lacked a second question have one, and selection avoids repeats."""
import pytest

from backend.ingestion import DocumentMetadata
from backend.models import Paper, StudyProgress
from backend.session import LearningSession, session_manager
from backend.tutor import quiz_session as quiz
from backend.tutor.quiz_bank import QUIZ_BANK

pytestmark = pytest.mark.prereqai


def _session(*planned):
    paper = Paper(source_path="x.pdf", metadata=DocumentMetadata(title="T", author="A", subject="", keywords="", creator="", producer="", page_count=1))
    paper.study_progress = [StudyProgress(name, False, 0) for name in planned]
    session = LearningSession()
    session.paper = paper
    return session


def _answer(session, concept, outcome="knew", number=None):
    asked = quiz.next_question(session, concept) if number is None else None
    identifier = asked["question_id"] if asked else quiz.question_id(concept, number)
    session.quiz_pending.setdefault(identifier, {"revealed": False})
    quiz.reveal(session, identifier)
    return quiz.record(session, identifier, outcome), identifier


def _status(session, concept):
    return next(e for e in quiz.progress(session)["concepts"] if e["concept"] == concept)


def test_the_same_question_answered_correctly_twice_is_not_mastery():
    session = _session("Transformer")
    for _ in range(3):
        _answer(session, "Transformer", number=1)
    entry = _status(session, "Transformer")
    assert entry["knew"] == 3 and quiz.distinct_knew(session, "Transformer") == 1 and entry["status"] == "progressing"
    assert quiz.known_suggestions(session) == []


@pytest.mark.parametrize("concept", ["Transformer", "Markov Decision Process", "Attention"])
def test_two_different_questions_give_mastery_and_a_known_suggestion(concept):
    session = _session(concept)
    for number in (1, 2, 3):  # three answers, the last two on different questions after a repeat of the first
        _answer(session, concept, number=number if number < 3 else 2)
    _answer(session, concept, number=1)
    entry = _status(session, concept)
    assert entry["status"] == "mastered" and quiz.distinct_knew(session, concept) >= 2
    assert [item["concept"] for item in quiz.known_suggestions(session)] == [concept]


def test_a_repeated_question_never_adds_to_the_distinct_count_even_if_written_differently():
    session = _session("Softmax")
    _answer(session, "Softmax", number=1)
    session.quiz_pending["Softmax:1"] = {"revealed": False}
    quiz.record(session, "Softmax:01", "knew")  # the same question written another way
    assert {a["question_id"] for a in session.quiz_attempts} == {"Softmax:1"} and quiz.distinct_knew(session, "Softmax") == 1
    with pytest.raises(quiz.QuizError):
        quiz.next_question(session, "Softmax:²") if False else quiz._lookup("Softmax:²")  # a look-alike digit is not a question


def test_a_missed_answer_between_breaks_the_streak_as_before():
    session = _session("Transformer")
    _answer(session, "Transformer", number=1)
    _answer(session, "Transformer", "missed", number=2)
    _answer(session, "Transformer", number=3)
    assert _status(session, "Transformer")["status"] == "progressing"
    _answer(session, "Transformer", number=1)
    assert _status(session, "Transformer")["status"] == "mastered"


def test_the_concepts_that_lacked_a_second_question_have_one_and_the_ids_did_not_change():
    for name in ("Transformer", "Markov Decision Process", "Attention", "Softmax", "Backpropagation", "Positional Encoding", "Policy Gradient"):
        assert len(QUIZ_BANK[name]) >= 2, name
    assert len(QUIZ_BANK["Transformer"]) >= 3 and len(QUIZ_BANK["Markov Decision Process"]) >= 3 and len(QUIZ_BANK["Attention"]) >= 3
    assert QUIZ_BANK["Transformer"][0]["question"] == "Why are positional encodings required?"  # appended, never inserted


def test_every_question_is_valid_distinct_and_explains_its_answer():
    for name, items in QUIZ_BANK.items():
        questions = [item["question"].strip().lower() for item in items]
        assert len(set(questions)) == len(questions), name  # no duplicate within a concept
        for item in items:
            assert item["question"].strip() and item["difficulty"] in ("Easy", "Medium", "Hard")
            assert len(item["answer"].split()) >= 5, (name, item["question"])  # an explanation, not a one-word answer


def test_selection_does_not_repeat_the_last_answered_question_when_another_exists():
    session = _session("Transformer")
    seen = []
    for _ in range(7):
        _, identifier = _answer(session, "Transformer")
        seen.append(identifier)
    assert all(a != b for a, b in zip(seen, seen[1:])) and set(seen) == {"Transformer:1", "Transformer:2", "Transformer:3"}
    twin = _session("Transformer")
    assert [_answer(twin, "Transformer")[1] for _ in range(7)] == seen  # deterministic


def test_a_topic_with_a_single_question_is_served_gracefully_and_cannot_reach_mastery():
    single = next(name for name, items in quiz.ASKABLE.items() if len(items) == 1)
    session = _session(single)
    ids = [_answer(session, single)[1] for _ in range(3)]
    assert set(ids) == {f"{single}:1"} and _status(session, single)["status"] == "progressing"
    assert quiz.known_suggestions(session) == []


def test_mastery_is_rebuilt_from_the_attempts_after_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    session = session_manager.create("T", {}, _session("Transformer").paper)
    for number in (1, 2):
        _answer(session, "Transformer", number=number)
    before = _status(session, "Transformer")
    session_manager.save(session)
    session_manager.sessions.clear()
    restored = session_manager.get(session.session_id)
    assert _status(restored, "Transformer") == before and before["status"] == "mastered"
    session_manager.sessions.clear()
