"""A worker that holds a session in memory sees what another worker saved without having to save itself first, and keeps its own unsaved changes."""
import pytest

from backend.platform import platform
from backend.progress import StudyProgressTracker
from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"


@pytest.fixture
def workers(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    sid = platform.analyze(SAMPLE)["session_id"]
    first, second = SessionManager(), SessionManager()
    return sid, first, second, first.get(sid), second.get(sid)


def _study(session, concept):
    StudyProgressTracker().complete(session.paper, concept)
    platform._refresh_progress(session.paper, session.report)


def _studied(session):
    return {item.concept for item in session.paper.study_progress if item.completed}


def test_a_read_sees_the_other_workers_saved_change_without_saving(workers):
    sid, first, second, a, b = workers
    concept = [item.concept for item in a.paper.study_progress][0]
    _study(a, concept)
    first.save(a)
    assert concept not in _studied(b)  # the second worker's copy is still the old one ...
    assert concept in _studied(second.get(sid))  # ... until it reads again
    assert second.get(sid) is b  # the same object, so requests in flight keep working on it
    assert b.version == a.version


def test_the_readers_own_unsaved_change_survives_the_refresh(workers):
    sid, first, second, a, b = workers
    plan = [item.concept for item in a.paper.study_progress]
    _study(a, plan[0])
    first.save(a)
    _study(b, plan[1])  # not saved yet
    seen = second.get(sid)
    assert {plan[0], plan[1]} <= _studied(seen)
    second.save(seen)
    assert {plan[0], plan[1]} <= _studied(first.get(sid))  # and a later save loses nothing either way


def test_an_unchanged_file_is_not_read_again(workers, monkeypatch):
    sid, first, second, a, b = workers
    reads = []
    original = SessionManager._read_file
    monkeypatch.setattr(SessionManager, "_read_file", staticmethod(lambda path: reads.append(path) or original(path)))
    for _ in range(5):
        second.get(sid)
    assert reads == []
    first.save(a)
    reads.clear()  # the saving worker reads the file itself to merge; only the other worker's reads count
    second.get(sid)
    second.get(sid)
    assert len(reads) == 1


def test_an_unreadable_file_leaves_the_held_session_alone_but_a_missing_one_means_it_was_deleted(workers):
    sid, first, second, a, b = workers
    path = second._path(sid)
    path.write_bytes(b"not a session")
    assert second.get(sid) is b
    path.unlink()  # a file that vanished after this worker saw it was deleted by another worker (see the tests below)
    assert second.get(sid) is None


def test_a_session_another_worker_deleted_is_not_served_any_more(workers):
    sid, first, second, a, b = workers
    assert first.delete(sid) is True
    assert second.get(sid) is None and sid not in second.sessions
    assert second.get(sid) is None


def test_a_stale_worker_cannot_bring_a_deleted_session_back_by_saving(workers, tmp_path):
    sid, first, second, a, b = workers
    first.delete(sid)
    _study(b, "Linear Algebra")  # worker two still holds the object and changes it
    assert second.save(b) is False
    assert not (tmp_path / f"{sid}.session").exists() and sid not in second.sessions
    assert first.get(sid) is None


def test_deletion_wins_over_this_workers_unsaved_change_but_a_session_never_saved_is_unaffected(workers, tmp_path):
    sid, first, second, a, b = workers
    first.delete(sid)
    _study(b, "Calculus")
    assert second.get(sid) is None  # the unsaved change is dropped with the session: deletion is explicit, a changed copy is not a reason to undo it
    fresh = SessionManager().create("Never saved elsewhere")
    assert SessionManager.save(second, fresh) is True and (tmp_path / f"{fresh.session_id}.session").exists()


def test_a_session_this_worker_deleted_itself_can_be_created_again_and_ordinary_reads_still_work(workers, tmp_path):
    sid, first, second, a, b = workers
    assert first.get(sid) is a and second.get(sid) is b
    _study(a, "Probability")
    assert first.save(a) is True
    assert "Probability" in _studied(second.get(sid))
    second.delete(sid)
    assert first.get(sid) is None and not (tmp_path / f"{sid}.session").exists()
