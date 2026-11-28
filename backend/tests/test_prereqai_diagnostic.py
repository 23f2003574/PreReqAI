"""Objectively graded diagnostics: options are fixed and checked by the system, confidence is stored apart from correctness, self-reported answers alone never establish mastery, and old profiles migrate."""
import json
import multiprocessing
from types import SimpleNamespace

from datetime import datetime, timedelta, timezone

import pytest

from backend import learner_profile
from backend.tutor import diagnostic, quiz_session
from backend.tutor.quiz_session import QuizError

pytestmark = pytest.mark.prereqai
CONCEPT = "Softmax"


def session():
    return SimpleNamespace(quiz_pending={}, quiz_attempts=[], paper=SimpleNamespace(concepts=[SimpleNamespace(name=CONCEPT)]))


def serve_and_answer(s, concept, picker, confidence="medium"):
    question = diagnostic.serve(s, concept)
    options = question["options"]
    index = picker(question, options)
    return question, diagnostic.grade(s, question["question_id"], index, confidence)


def right(question, options):
    return options.index(quiz_session._lookup(question["question_id"])[2]["answer"])


def wrong(question, options):
    return 0 if options[0] != quiz_session._lookup(question["question_id"])[2]["answer"] else 1


def test_options_are_four_distinct_fixed_texts_including_the_answer_and_served_without_it():
    s = session()
    question = diagnostic.serve(s, CONCEPT)
    answer = quiz_session._lookup(question["question_id"])[2]["answer"]
    assert len(question["options"]) == 4 and len(set(question["options"])) == 4 and answer in question["options"] and "answer" not in question
    assert diagnostic.options_for(question["question_id"]) == question["options"] == diagnostic.options_for(question["question_id"])  # the same on every request
    assert question["graded"] is True and question["confidence_levels"] == ["low", "medium", "high"]


def test_the_system_grades_the_choice_and_stores_correctness_and_confidence_apart():
    s = session()
    question, verdict = serve_and_answer(s, CONCEPT, right, "high")
    assert verdict["correct"] is True and verdict["confidence"] == "high"
    attempt = s.quiz_attempts[-1]
    assert attempt["graded"] is True and attempt["correct"] is True and attempt["confidence"] == "high" and attempt["outcome"] == "knew" and s.quiz_pending == {}
    _, bad = serve_and_answer(s, CONCEPT, wrong, "high")
    assert bad["correct"] is False and "sure and it was wrong" in bad["calibration"] and s.quiz_attempts[-1]["outcome"] == "missed"
    assert diagnostic.assessed_summary(s)[CONCEPT] == {"graded": 2, "correct": 1, "high_confidence_wrong": 1}


@pytest.mark.parametrize("choice, confidence, kind", [(9, "high", "outcome"), (-1, "high", "outcome"), (True, "high", "outcome"), ("1", "high", "outcome"), (0, "certain", "outcome")])
def test_invalid_choices_and_confidences_are_refused_without_recording(choice, confidence, kind):
    s = session()
    question = diagnostic.serve(s, CONCEPT)
    with pytest.raises(QuizError) as error:
        diagnostic.grade(s, question["question_id"], choice, confidence)
    assert error.value.kind == kind and s.quiz_attempts == [] and question["question_id"] in s.quiz_pending


def test_a_question_that_was_not_served_or_is_already_answered_is_refused():
    s = session()
    with pytest.raises(QuizError) as error:
        diagnostic.grade(s, "Softmax:1", 0, "low")
    assert error.value.kind == "state"
    question, _ = serve_and_answer(s, CONCEPT, right)
    with pytest.raises(QuizError):
        diagnostic.grade(s, question["question_id"], 0, "low")


def _master(path, concept, graded):
    for number in (1, 2):
        for day in (2, 0):  # answered on two different days: one sitting is not durable mastery (backend/mastery_model.py)
            learner_profile.record_quiz(path, f"{concept}:{number}", concept, "knew", moment=datetime.now(timezone.utc) - timedelta(days=day, minutes=-number), graded={"correct": True, "confidence": "medium"} if graded else None)


def status(path, concept):
    return {m["concept"]: m for m in learner_profile.mastery(learner_profile.load_full(path)[0]["quiz"])}[concept]


def test_self_reported_answers_alone_never_establish_mastery_but_assessed_ones_do(tmp_path):
    path = tmp_path / "p.json"
    _master(path, "Probability", graded=False)
    assert status(path, "Probability")["status"] == "self_reported" and status(path, "Probability")["evidence"] == "self_reported"
    assert "Probability" not in learner_profile.mastered(learner_profile.load_full(path)[0]["quiz"])
    _master(path, "Calculus", graded=True)
    calculus = status(path, "Calculus")
    assert calculus["status"] == "mastered" and calculus["evidence"] == "assessed" and calculus["graded_attempts"] == 4 and calculus["graded_correct"] == 4
    assert set(learner_profile.mastered(learner_profile.load_full(path)[0]["quiz"])) == {"Calculus"}


def test_confidently_wrong_answers_block_mastery_and_a_miss_needs_practice(tmp_path):
    path = tmp_path / "p.json"
    for number in (1, 2):
        learner_profile.record_quiz(path, f"Statistics:{number}", "Statistics", "missed", graded={"correct": False, "confidence": "high"})
        for _ in range(3):
            learner_profile.record_quiz(path, f"Statistics:{number}", "Statistics", "knew", graded={"correct": True, "confidence": "low"})
    item = status(path, "Statistics")
    assert item["high_confidence_wrong"] == 2 and item["status"] == "progressing"  # right now, but twice confidently wrong: not mastered
    learner_profile.record_quiz(path, "Statistics:1", "Statistics", "missed", graded={"correct": False, "confidence": "low"})
    assert status(path, "Statistics")["status"] == "needs_practice"


def test_a_profile_saved_before_assessed_answers_migrates_without_losing_history(tmp_path):
    path = tmp_path / "old.json"
    entry = {"concept": "Softmax", "attempts": 4, "knew": 3, "missed": 1, "streak": 3, "last_outcome": "knew", "first_seen": "2026-11-01T00:00:00Z", "last_seen": "2026-11-05T00:00:00Z",
             "interval_hours": 96.0, "due": "2026-11-09T00:00:00Z"}
    path.write_text(json.dumps({"format": learner_profile.FORMAT, "schema_version": 2, "known": ["Calculus"], "studied": [], "quiz": {"Softmax:1": entry}}), encoding="utf-8")
    profile, problem = learner_profile.load_full(path)
    assert problem == "" and profile["quiz"]["Softmax:1"] == entry  # read as it was: no invented assessment
    learner_profile.record_quiz(path, "Softmax:1", "Softmax", "knew", graded={"correct": True, "confidence": "high"})
    saved = json.loads(path.read_text(encoding="utf-8"))
    kept = saved["quiz"]["Softmax:1"]
    assert saved["schema_version"] == 3 and saved["known"] == ["Calculus"] and kept["attempts"] == 5 and kept["knew"] == 4 and kept["missed"] == 1 and kept["first_seen"] == entry["first_seen"]
    assert kept["graded_attempts"] == 1 and kept["graded_correct"] == 1 and kept["graded_streak"] == 1 and kept["high_confidence_right"] == 1 and kept["high_confidence_wrong"] == 0


def test_invalid_assessment_counters_are_rejected_and_the_file_is_untouched(tmp_path):
    entry = {"concept": "Softmax", "attempts": 1, "knew": 1, "missed": 0, "streak": 1, "last_outcome": "knew", "first_seen": "2026-11-01T00:00:00Z", "last_seen": "2026-11-01T00:00:00Z",
             "interval_hours": 24.0, "due": "2026-11-02T00:00:00Z", "graded_attempts": 1, "graded_correct": 5}
    raw = json.dumps({"format": learner_profile.FORMAT, "schema_version": 2, "known": [], "studied": [], "quiz": {"Softmax:1": entry}}).encode()
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.parse_full(raw)


def _record(args):
    path, number = args
    for _ in range(5):
        learner_profile.record_quiz(path, f"Softmax:{number}", "Softmax", "knew", graded={"correct": True, "confidence": "medium"})


def test_four_processes_recording_assessed_answers_lose_none(tmp_path):
    path = str(tmp_path / "shared.json")
    context = multiprocessing.get_context("spawn")
    with context.Pool(4) as pool:
        pool.map(_record, [(path, number) for number in (1, 1, 2, 2)])
    quiz = learner_profile.load_full(path)[0]["quiz"]
    assert sum(e["graded_attempts"] for e in quiz.values()) == 20 and sum(e["attempts"] for e in quiz.values()) == 20


def _days(sequence):
    from datetime import datetime, timedelta, timezone

    start = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    return [start + timedelta(days=i) for i in range(len(sequence))]


def _run(*flags, confidence="high"):
    from backend import mastery_model

    answers = [(flag, confidence, f"q{i}") for i, flag in enumerate(flags)]
    return mastery_model.estimate(answers, _days(answers))


def test_a_recent_miss_blocks_durable_mastery_even_when_the_probability_stays_high():
    for flags in ((True,) * 5 + (False,), (True,) * 5 + (False, False), (True,) * 4 + (False, True)):
        for confidence in ("medium", "high"):
            result = _run(*flags, confidence=confidence)
            assert result["recent_miss"] is True and result["mastered"] is False and "recent_miss" in result["reason"], (flags, confidence)
    assert _run(*((True,) * 5 + (False,)))["p"] > 0.9  # the probability alone would have said mastered


def test_two_correct_answers_after_a_miss_restore_mastery_without_discarding_the_earlier_evidence():
    recovered = _run(*((True,) * 8 + (False, True, True)), confidence="medium")  # a history with a miss must also show sustained accuracy (Wilson lower bound 0.70): 10 of 11 does, 7 of 8 does not
    assert recovered["recent_miss"] is False and recovered["mastered"] is False and "sustained" in recovered["reason"]
    recovered = _run(*((True,) * 11 + (False, True, True)), confidence="medium")
    assert recovered["recent_miss"] is False and recovered["mastered"] is True and recovered["answers"] == 14
    assert _run(*((True,) * 5 + (False, True)), confidence="medium")["mastered"] is False  # one correct answer is not yet two in a row


def test_a_miss_long_ago_does_not_count_as_recent_and_the_order_is_the_time_order_not_the_list_order():
    from datetime import timedelta

    from backend import mastery_model

    assert _run(False, True, True, True, True, True)["recent_miss"] is False
    answers = [(True, "high", f"q{i}") for i in range(5)] + [(False, "high", "q9")]
    times = _days(answers)
    times[-1] = times[0] - timedelta(days=1)  # the miss happened first, though it is listed last
    result = mastery_model.estimate(answers, times)
    assert result["recent_miss"] is False


def _fresh_session():
    from backend.session import session_manager

    return session_manager.create("Option order")


def _serve_and_answer(session, concept, pick):
    """Serve the next question of `concept`, answer by `pick(options, answer)`; (served, verdict)."""
    served = diagnostic.serve(session, concept)
    _, _, item = quiz_session._lookup(served["question_id"])
    verdict = diagnostic.grade(session, served["question_id"], pick(served["options"], item["answer"]), "medium")
    return served, verdict, item["answer"]


def test_a_question_served_again_shows_the_same_four_options_in_a_different_order_and_grades_by_text():
    session, concept = _fresh_session(), "Softmax"
    orders = []
    for _ in range(4):  # the concept has two or three questions, so the same question comes back
        served, verdict, answer = _serve_and_answer(session, concept, lambda options, answer: options.index(answer))
        orders.append((served["question_id"], tuple(served["options"])))
        assert verdict["correct"] is True and sorted(served["options"]) == sorted(diagnostic.options_for(served["question_id"]))
    by_question = {}
    for question, order in orders:
        by_question.setdefault(question, []).append(order)
    repeated = [seen for seen in by_question.values() if len(seen) > 1]
    assert repeated and all(seen[i] != seen[i + 1] for seen in repeated for i in range(len(seen) - 1))
    assert all(seen[0] == tuple(diagnostic.options_for(question)) for question, seen in by_question.items())  # the first serving is the fixed order


def test_a_wrong_choice_is_judged_by_the_text_shown_in_the_stored_order_not_the_regenerated_one():
    session, concept = _fresh_session(), "Softmax"
    _serve_and_answer(session, concept, lambda options, answer: options.index(answer))
    served = diagnostic.serve(session, concept)
    shown = list(served["options"])
    stored = session.quiz_pending[served["question_id"]]["options"]
    assert stored == shown
    _, _, item = quiz_session._lookup(served["question_id"])
    wrong = next(i for i, text in enumerate(shown) if text != item["answer"])
    assert diagnostic.grade(session, served["question_id"], wrong, "medium")["correct"] is False
    assert session.quiz_attempts[-1]["chosen"] == shown[wrong]


def test_reloading_a_pending_question_keeps_its_order_and_a_pending_question_of_an_older_session_uses_the_fixed_order():
    session, concept = _fresh_session(), "Softmax"
    _serve_and_answer(session, concept, lambda options, answer: options.index(answer))
    first = diagnostic.serve(session, concept)
    assert diagnostic.serve(session, concept)["options"] == first["options"]  # served again before it is answered
    session.quiz_pending[first["question_id"]] = {"revealed": False}  # an older session: no stored order
    _, _, item = quiz_session._lookup(first["question_id"])
    fixed = diagnostic.options_for(first["question_id"])
    assert diagnostic.grade(session, first["question_id"], fixed.index(item["answer"]), "high")["correct"] is True


def test_the_stored_order_survives_saving_and_reading_the_session(tmp_path, monkeypatch):
    from backend.session.session_manager import SessionManager

    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    manager = SessionManager()
    session = manager.create("Persisted order")
    _serve_and_answer(session, "Softmax", lambda options, answer: options.index(answer))
    served = diagnostic.serve(session, "Softmax")
    assert manager.save(session) is True
    reread = SessionManager().get(session.session_id)
    assert reread.quiz_pending[served["question_id"]]["options"] == served["options"]
    _, _, item = quiz_session._lookup(served["question_id"])
    assert diagnostic.grade(reread, served["question_id"], served["options"].index(item["answer"]), "medium")["correct"] is True


def test_correctness_does_not_depend_on_where_the_right_option_stands():
    for concept in ("Softmax", "Calculus"):
        for attempt in range(6):
            for question_id in (quiz_session.question_id(concept, 1), quiz_session.question_id(concept, 2)):
                order = diagnostic.order_for_attempt(question_id, attempt)
                assert sorted(order) == sorted(diagnostic.options_for(question_id)) and len(set(order)) == len(order) == diagnostic.OPTIONS
                if attempt:
                    assert order != diagnostic.order_for_attempt(question_id, attempt - 1)
