"""A new paper's adaptive plan uses what the learner's persistent profile shows: fresh, assessed mastery shortens (or skips) a step with the reason named; stale, self-reported or thin evidence never does."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from backend import adaptive_plan, learner_profile, spaced_review

pytestmark = pytest.mark.prereqai
NOW = spaced_review.now()


def report(**extra):
    return {"learning_plan": [{"concept": "Calculus", "estimated_hours": 4.0}, {"concept": "Probability", "estimated_hours": 3.0}],
            "math_plan": [{"concept": "Math: Entropy", "estimated_hours": 2.0}],
            "missing_prerequisites": [{"concept": "Calculus", "importance": "essential"}], "study_progress": [], **extra}


def entries(concept, due_in_days=30, graded=True, last_outcome="knew", seen_days_ago=1):
    base = {"concept": concept, "attempts": 2, "knew": 2, "missed": 0, "streak": 2, "last_outcome": last_outcome, "first_seen": "2026-10-01T00:00:00Z", "last_seen": spaced_review.stamp(NOW - timedelta(days=seen_days_ago)),
            "interval_hours": 72.0, "due": spaced_review.stamp(NOW + timedelta(days=due_in_days)), **({"graded_attempts": 2, "graded_correct": 2, "graded_streak": 2} if graded else {})}
    return {f"{concept}:1": dict(base), f"{concept}:2": dict(base)}


def adjustment(result, concept):
    return next((a for a in result["adjustments"] if a["concept"] == concept), None)


def test_fresh_assessed_mastery_in_the_profile_shortens_the_step_and_names_the_profile():
    result = adaptive_plan.propose(report(), [], None, None, entries("Calculus"))
    change = adjustment(result, "Calculus")
    assert change["action"] == "compress" and change["adjusted_hours"] == 1.2 and change["evidence"]["source"] == "profile" and "learner profile" in change["reason"]
    assert result["hours_after"] < result["hours_before"] and adjustment(result, "Probability") is None


def test_a_mathematical_skill_demonstrated_in_the_profile_is_skipped():
    result = adaptive_plan.propose(report(), [], None, None, entries("Math: Entropy"))
    assert adjustment(result, "Math: Entropy")["action"] == "skip" and adjustment(result, "Math: Entropy")["adjusted_hours"] == 0.0


@pytest.mark.parametrize("quiz", [entries("Calculus", seen_days_ago=60), entries("Calculus", graded=False), entries("Calculus", last_outcome="missed"), {}, None])
def test_stale_self_reported_missed_or_absent_profile_evidence_never_changes_the_plan(quiz):
    result = adaptive_plan.propose(report(), [], None, None, quiz)
    assert adjustment(result, "Calculus") is None and result["hours_after"] == result["hours_before"]


def test_this_sessions_own_answers_win_over_the_profile_and_the_user_can_reverse_the_change():
    own = [{"concept": "Calculus", "graded": True, "correct": False, "question_id": "Calculus:1", "confidence": "medium"}]
    assert adjustment(adaptive_plan.propose(report(), own, None, None, entries("Calculus")), "Calculus")["evidence"].get("source") is None
    rejected = adaptive_plan.propose(report(), [], {"Calculus": "reject"}, None, entries("Calculus"))
    assert adjustment(rejected, "Calculus")["overridden"] and adjustment(rejected, "Calculus")["adjusted_hours"] == 4.0 and rejected["hours_after"] == rejected["hours_before"]


def test_without_a_profile_the_proposal_is_exactly_what_it_was():
    assert adaptive_plan.propose(report(), [], None, None) == adaptive_plan.propose(report(), [], None, None, None)


def test_the_session_report_adapts_from_the_saved_profile_unless_the_extraction_is_unreliable(tmp_path, monkeypatch):
    monkeypatch.setenv(learner_profile.PROFILE_DIR_ENV, str(tmp_path))
    learner_profile.save(tmp_path / "me.json", [], [], entries("Calculus"))
    session = SimpleNamespace(profile="me", report=report(), quiz_attempts=[])
    adapted = adaptive_plan.session_report(session)
    assert adapted["adapted_concepts"] == ["Calculus"] and adapted["learning_plan"][0]["estimated_hours"] == 1.2 and adapted["learning_plan"][0]["original_hours"] == 4.0
    guarded = SimpleNamespace(profile="me", report=report(confidence_effects={"guard_adaptation": True}), quiz_attempts=[])
    assert adaptive_plan.session_report(guarded) is guarded.report
    assert adaptive_plan.session_report(SimpleNamespace(profile=None, report=report(), quiz_attempts=[]))["learning_plan"][0]["estimated_hours"] == 4.0
    (tmp_path / "me.json").write_text("not json")
    assert adaptive_plan.profile_quiz(session) is None and adaptive_plan.session_report(session)["learning_plan"][0]["estimated_hours"] == 4.0
