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


def test_a_deleted_or_unreadable_file_leaves_the_held_session_alone(workers):
    sid, first, second, a, b = workers
    path = second._path(sid)
    path.write_bytes(b"not a session")
    assert second.get(sid) is b
    path.unlink()
    assert second.get(sid) is b
