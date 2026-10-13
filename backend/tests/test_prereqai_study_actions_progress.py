"""Study actions follow study progress: a concept the learner finished is no longer an action to take."""
from pathlib import Path

from backend.platform import platform
from backend.session import session_manager

SAMPLE = str(Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf")


def _titles(report):
    return [action["title"] for action in report["study_actions"]]


def test_studied_at_analysis_removes_the_action_and_a_later_reset_restores_it():
    outcome = platform.analyze(SAMPLE, studied=["Probability"])
    assert "Study Probability" not in _titles(outcome["report"])
    assert "Study Linear Algebra" in _titles(outcome["report"])

    sid = outcome["session_id"]
    platform.unmark_concept_studied(sid, "Probability")
    assert "Study Probability" in _titles(session_manager.get(sid).report)


def test_marking_a_concept_studied_later_updates_the_session_report_but_not_other_actions():
    sid = platform.analyze(SAMPLE)["session_id"]
    before = _titles(session_manager.get(sid).report)
    assert "Study Calculus" in before

    platform.mark_concept_studied(sid, "calculus")
    after = _titles(session_manager.get(sid).report)
    assert after == [title for title in before if title != "Study Calculus"]
