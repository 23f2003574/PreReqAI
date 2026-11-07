"""A session whose latest save failed holds progress only in memory, so eviction keeps it; saved sessions are still evicted."""
from backend.session import session_manager


def test_eviction_keeps_a_session_whose_save_failed(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(blocker))  # every save fails
    monkeypatch.setattr(type(session_manager), "MAX_SESSIONS_IN_MEMORY", 1)
    session_manager.sessions.clear()
    first = session_manager.create("First")
    first.created_at = 1.0
    second = session_manager.create("Second")
    second.created_at = 2.0
    assert session_manager.get(first.session_id) is first  # still there, with its unsaved progress
    assert session_manager.get(second.session_id) is second


def test_eviction_still_drops_saved_sessions_and_they_restore(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(type(session_manager), "MAX_SESSIONS_IN_MEMORY", 1)
    session_manager.sessions.clear()
    first = session_manager.create("First")
    first.created_at = 1.0
    session_manager.create("Second").created_at = 2.0
    assert first.session_id not in session_manager.sessions
    assert session_manager.get(first.session_id).paper_title == "First"
