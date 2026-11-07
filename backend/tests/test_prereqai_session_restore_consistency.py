"""A saved session that lists a concept as both studied and already known is made consistent when it is restored."""
import pymupdf as fitz

from backend.models import StudyProgress
from backend.platform import platform
from backend.session import session_manager


def _analyze(tmp_path):
    document = fitz.open()
    document.new_page().insert_textbox(fitz.Rect(72, 72, 540, 760), "Abstract\nWe train a policy gradient agent over a Markov decision process.\n")
    path = tmp_path / "p.pdf"
    document.save(path)
    return platform.analyze(str(path))


def test_known_and_studied_in_one_saved_file_is_reconciled_on_restore(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    sid = _analyze(tmp_path)["session_id"]
    paper = session_manager.get(sid).paper
    name = paper.learning_plan[0].concept
    platform.mark_concept_known(sid, name)
    session = session_manager.get(sid)
    session.paper.study_progress.append(StudyProgress(concept=name, completed=True, progress_percent=100))  # the contradiction
    session_manager.save(session)

    session_manager.sessions.clear()  # restart
    restored = session_manager.get(sid)
    assert name not in [item.concept for item in restored.paper.study_progress]
    assert name in restored.paper.studied_while_known
    assert name not in [item["concept"] for item in restored.report["study_progress"]]

    platform.unmark_concept_known(sid, name)  # the study progress it had comes back
    assert any(item.concept == name and item.completed for item in session_manager.get(sid).paper.study_progress)


def test_a_consistent_session_is_restored_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    sid = _analyze(tmp_path)["session_id"]
    platform.mark_concept_studied(sid, session_manager.get(sid).paper.learning_plan[0].concept)
    before = [(i.concept, i.completed) for i in session_manager.get(sid).paper.study_progress]
    session_manager.sessions.clear()
    assert [(i.concept, i.completed) for i in session_manager.get(sid).paper.study_progress] == before
