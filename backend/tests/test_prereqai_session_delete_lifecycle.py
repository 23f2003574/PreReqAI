"""Deleting a session releases everything the manager kept for it, in memory and on disk."""
import pytest

from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai


def test_deleting_sessions_leaves_no_bookkeeping_behind(monkeypatch):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    manager = SessionManager()

    for _ in range(50):
        assert manager.delete(manager.create("paper").session_id)

    assert manager.sessions == {} and manager._last_used == {}


def test_deleting_a_saved_session_forgets_its_file_and_cached_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    manager = SessionManager()
    kept, dropped = manager.create("kept"), manager.create("dropped")
    for session in (kept, dropped):  # saved-only: listed from disk, summaries cached
        manager.sessions.pop(session.session_id)
    assert len(manager.summaries()) == 2 and len(manager._summaries) == 2

    assert manager.delete(dropped.session_id)

    assert not (tmp_path / f"{dropped.session_id}.session").exists()
    assert [path.stem for path in manager._summaries] == [kept.session_id]
    assert [item["session_id"] for item in manager.summaries()] == [kept.session_id]
    assert manager._last_used.get(dropped.session_id) is None
