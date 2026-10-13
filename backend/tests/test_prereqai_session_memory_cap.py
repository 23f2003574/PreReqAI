"""A long-running server keeps a bounded number of sessions in memory."""
from backend.session import session_manager


def test_the_oldest_sessions_are_dropped_from_memory_past_the_cap(monkeypatch, tmp_path):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    monkeypatch.setattr(type(session_manager), "MAX_SESSIONS_IN_MEMORY", 3)
    session_manager.sessions.clear()
    created = []
    for index in range(5):
        session = session_manager.create(f"Paper {index}")
        session.created_at = float(index)
        created.append(session)
    session_manager._evict_oldest()

    assert set(session_manager.sessions) == {s.session_id for s in created[2:]}
    assert session_manager.get(created[0].session_id) is None and session_manager.get(created[4].session_id) is created[4]


def test_an_evicted_session_is_still_restored_from_disk_and_the_newest_is_never_evicted(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(type(session_manager), "MAX_SESSIONS_IN_MEMORY", 1)
    session_manager.sessions.clear()
    first = session_manager.create("First")
    first.created_at = 1.0
    session_manager.save(first)
    second = session_manager.create("Second")

    assert list(session_manager.sessions) == [second.session_id]
    assert session_manager.get(first.session_id).paper_title == "First"  # restored from its saved file


def test_an_active_old_session_outlives_an_idle_newer_one(monkeypatch):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    monkeypatch.setattr(type(session_manager), "MAX_SESSIONS_IN_MEMORY", 2)
    session_manager.sessions.clear()
    session_manager._last_used.clear()
    old = session_manager.create("Old but active")
    idle = session_manager.create("Newer but idle")
    session_manager._last_used[old.session_id], session_manager._last_used[idle.session_id] = 10.0, 20.0
    assert session_manager.get(old.session_id) is old  # the learner comes back to it: now the most recently used

    newest = session_manager.create("Newest")

    assert set(session_manager.sessions) == {old.session_id, newest.session_id}
    assert session_manager.get(idle.session_id) is None
