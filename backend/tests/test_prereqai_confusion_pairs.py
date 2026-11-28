"""Misconception and confusion-pair diagnosis: a wrong pick of another concept's answer is recorded, persisted and exported, recurring pairs reach the profile and the adaptive plan, and one wrong answer never moves mastery."""
import json
from types import SimpleNamespace

import pytest

from backend import adaptive_plan, learner_profile, mastery_model, spaced_review
from backend.tutor import diagnostic
from backend.tutor.quiz_session import ASKABLE

pytestmark = pytest.mark.prereqai
A, B = "Backpropagation", "Gradient Descent"


def test_the_answer_of_another_concept_is_traced_to_that_concept():
    assert diagnostic.option_origin(ASKABLE[B][0]["answer"], A) == B
    assert diagnostic.option_origin(ASKABLE[A][0]["answer"], A) is None and diagnostic.option_origin("no such answer", A) is None


def _graded_session(pick_other):
    session = SimpleNamespace(quiz_pending={}, quiz_attempts=[])
    identifier = f"{A}:1"
    session.quiz_pending[identifier] = {"options": [ASKABLE[A][0]["answer"], ASKABLE[B][0]["answer"], "x", "y"]}
    verdict = diagnostic.grade(session, identifier, 1 if pick_other else 0, "medium")
    return session.quiz_attempts[-1], verdict


def test_a_wrong_pick_records_the_confusion_and_a_right_answer_does_not():
    attempt, verdict = _graded_session(True)
    assert attempt["confused_with"] == B and not verdict["correct"]
    assert "confused_with" not in _graded_session(False)[0]


def test_confusions_persist_in_the_profile_and_export_and_recur_into_a_pair(tmp_path):
    path = tmp_path / "me.json"
    for _ in range(2):
        learner_profile.record_quiz(path, f"{A}:1", A, "missed", graded={"correct": False, "confidence": "medium", "confused_with": B})
    quiz = learner_profile.load_full(path)[0]["quiz"]
    assert quiz[f"{A}:1"]["confusions"] == {B: 2}
    pairs = learner_profile.confusion_pairs(quiz)
    assert pairs == [{"concept": A, "confused_with": B, "count": 2, "questions": [f"{A}:1"]}]
    assert json.loads(path.read_text())["quiz"][f"{A}:1"]["confusions"] == {B: 2}  # exported with the profile file
    learner_profile.record_quiz(path, f"{A}:2", A, "missed", graded={"correct": False, "confidence": "medium", "confused_with": "Softmax"})
    assert len(learner_profile.confusion_pairs(learner_profile.load_full(path)[0]["quiz"])) == 1  # a single slip is not a recurring confusion


def test_a_single_distractor_pick_does_not_change_the_mastery_estimate():
    without = mastery_model.estimate([(True, "medium", "q1"), (False, "medium", "q2")])
    assert without == mastery_model.estimate([(True, "medium", "q1"), (False, "medium", "q2")])  # the estimate takes no confusion input at all
    import inspect

    assert "confus" not in inspect.getsource(mastery_model.estimate)


def test_the_adaptive_plan_reports_a_recurring_confusion_with_advice():
    report = {"learning_plan": [], "math_plan": [], "missing_prerequisites": []}
    attempts = [{"graded": True, "correct": False, "concept": A, "confused_with": B, "question_id": f"{A}:1", "confidence": "medium"}] * 2
    result = adaptive_plan.propose(report, attempts)
    assert result["confusions"][0]["concept"] == A and result["confusions"][0]["confused_with"] == B and "differ" in result["confusions"][0]["advice"]
