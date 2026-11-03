"""Sessions created at the same instant are listed in one fixed order, however they were inserted or found on disk."""
import pytest

from backend.session.session_manager import SessionManager

pytestmark = pytest.mark.prereqai


def _manager(tmp_path, monkeypatch, reverse):
    monkeypatch.delenv("PREREQAI_SESSION_DIR", raising=False)
    manager = SessionManager()
    sessions = [manager.create(f"paper {i}") for i in range(4)]
    for session in sessions:
        session.created_at = 100.0
    if reverse:
        manager.sessions = dict(reversed(list(manager.sessions.items())))
    return manager


def test_equal_timestamps_list_in_the_same_order_whatever_the_insertion_order(tmp_path, monkeypatch):
    first = _manager(tmp_path, monkeypatch, reverse=False)
    second = _manager(tmp_path, monkeypatch, reverse=True)
    ids = lambda items: [getattr(item, "session_id", None) or item["session_id"] for item in items]

    assert ids(first.list()) == sorted(ids(first.list()), reverse=True)
    assert ids(first.summaries()) == sorted(ids(first.summaries()), reverse=True)
    assert ids(second.list()) == sorted(ids(second.list()), reverse=True)
    assert ids(second.summaries()) == ids(second.list())


def test_newer_sessions_still_come_first(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch, reverse=False)
    newest = manager.create("newest")
    newest.created_at = 200.0

    assert manager.list()[0] is newest
    assert manager.summaries()[0]["session_id"] == newest.session_id
