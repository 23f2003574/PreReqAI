"""Objectively graded diagnostics: options are fixed and checked by the system, confidence is stored apart from correctness, self-reported answers alone never establish mastery, and old profiles migrate."""
import json
import multiprocessing
from types import SimpleNamespace

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
        for _ in range(2):
            learner_profile.record_quiz(path, f"{concept}:{number}", concept, "knew", graded={"correct": True, "confidence": "medium"} if graded else None)


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
