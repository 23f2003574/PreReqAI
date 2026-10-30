"""A failed 'mark known' rebuild leaves the session exactly as it was, including the note that a concept was studied."""
import pytest

from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _done(sid):
    return {item.concept for item in session_manager.get(sid).paper.study_progress if item.completed}


def test_failed_mark_known_does_not_leave_a_stale_studied_note(monkeypatch):
    sid = platform.analyze(SAMPLE)["session_id"]
    platform.mark_concept_studied(sid, "Probability")
    with monkeypatch.context() as patch:
        patch.setattr(type(platform), "_personalize", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(RuntimeError):
            platform.mark_concept_known(sid, "Probability")
    assert getattr(session_manager.get(sid).paper, "studied_while_known", []) == []
    # the learner then un-studies it, marks it known and changes their mind: it must not come back as studied
    platform.unmark_concept_studied(sid, "Probability")
    platform.mark_concept_known(sid, "Probability")
    platform.unmark_concept_known(sid, "Probability")
    assert "Probability" not in _done(sid)


def test_a_successful_mark_known_still_restores_studied_progress_on_undo():
    sid = platform.analyze(SAMPLE)["session_id"]
    platform.mark_concept_studied(sid, "Probability")
    platform.mark_concept_known(sid, "Probability")
    platform.unmark_concept_known(sid, "Probability")
    assert "Probability" in _done(sid)
