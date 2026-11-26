"""Graded quiz attempts carry the time they were given, and the spacing rule applies to a session's own evidence: one sitting never skips a mathematical step."""
from datetime import datetime, timedelta, timezone

import pytest

from backend import adaptive_plan, mastery_model, spaced_review
from backend.session import session_manager
from backend.tutor import diagnostic, quiz_session

pytestmark = pytest.mark.prereqai
T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)


def attempt(question, hours, correct=True, concept="Math: Linear Algebra"):
    return {"question_id": question, "concept": concept, "outcome": "knew" if correct else "missed", "revealed": False, "graded": True, "correct": correct, "confidence": "high",
            "at": spaced_review.stamp(T0 + timedelta(hours=hours))}


SITTING = [attempt(q, i / 60) for i, q in enumerate(["a:1", "a:2", "a:1", "a:2", "a:1"])]
SPACED = [attempt("a:1", 0), attempt("a:2", 0.1), attempt("a:1", 30), attempt("a:2", 30.1)]


def test_a_graded_diagnostic_answer_records_when_it_was_given():
    session = session_manager.create("Timed")
    concept = next(iter(quiz_session.ASKABLE))
    before = spaced_review.now()
    question = diagnostic.serve(session, concept)
    diagnostic.grade(session, question["question_id"], 0, "medium")
    recorded = spaced_review.parse_time(session.quiz_attempts[-1]["at"])
    assert before - timedelta(seconds=2) <= recorded <= spaced_review.now() + timedelta(seconds=2)


def test_one_sitting_of_session_answers_is_not_durable_mastery():
    result = mastery_model.estimate_attempts(SITTING)
    assert result["timed"] is True and result["spaced_blocks"] == 1 and result["mastered"] is False
    assert mastery_model.estimate_attempts(SPACED)["mastered"] is True


def test_attempts_without_any_time_keep_the_earlier_behaviour_and_say_so():
    untimed = [{k: v for k, v in a.items() if k != "at"} for a in SITTING]
    result = mastery_model.estimate_attempts(untimed)
    assert result["timed"] is False and result["mastered"] is True


def test_a_math_step_is_not_skipped_on_one_sitting_or_on_untimed_evidence_but_is_on_spaced_evidence():
    untimed = [{k: v for k, v in a.items() if k != "at"} for a in SITTING]
    for attempts, skipped in ((SITTING, False), (untimed, False), (SPACED, True)):
        evidence = adaptive_plan.evidence_from_attempts(attempts)["Math: Linear Algebra"]
        action = adaptive_plan.decide("Math: Linear Algebra", 4.0, evidence)[0]
        assert (action == "skip") is skipped, (attempts[0].get("at"), action)
    assert adaptive_plan.decide("Math: Linear Algebra", 4.0, adaptive_plan.evidence_from_attempts(SITTING)["Math: Linear Algebra"])[0] in ("compress", "keep")


def _answers(flags, concept="Softmax"):
    return [{"question_id": f"{concept}:{n % 2 + 1}", "concept": concept, "outcome": "knew" if ok else "missed", "revealed": False, "graded": True, "correct": ok, "confidence": "medium",
             "at": spaced_review.stamp(T0 + timedelta(hours=n * 20))} for n, ok in enumerate(flags)]


def _action(flags):
    return adaptive_plan.decide("Softmax", 4.0, adaptive_plan.evidence_from_attempts(_answers(flags))["Softmax"])


def test_a_learner_who_missed_five_and_then_got_five_right_is_not_given_extra_time():
    action, factor, reason = _action([False] * 5 + [True] * 5)  # lifetime accuracy is exactly 50 percent, but the estimate is 0.6 and rising
    assert action == "keep" and factor == 1.0


def test_a_learner_who_is_still_struggling_is_still_given_extra_time_and_two_confident_misses_still_count():
    assert _action([False, False, True, False])[0] == "remediate"
    assert _action([False, False, True])[0] == "remediate"
    sure = [{**a, "confidence": "high"} for a in _answers([False, False, True, True, True, True])]
    assert adaptive_plan.decide("Softmax", 4.0, adaptive_plan.evidence_from_attempts(sure)["Softmax"])[0] == "remediate"


def test_the_recovered_learner_gets_no_remediation_in_the_proposed_plan():
    attempts = _answers([False] * 5 + [True] * 5, concept="Calculus")
    from backend.tests.test_prereqai_math_plan import report

    result = adaptive_plan.propose(report(), attempts)
    assert next((a for a in result["adjustments"] if a["concept"] == "Calculus"), {"action": "keep"})["action"] != "remediate"
