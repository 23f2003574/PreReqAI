"""Threads restoring the same saved session at once must all end up with one shared object, not one copy each."""
import threading

import pytest

from backend.session import session_manager

pytestmark = pytest.mark.prereqai


def test_concurrent_restores_of_one_saved_session_share_one_object(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("Paper", {"a": 1})
    session_id = session.session_id
    errors = []

    for _ in range(20):  # a real thread race: repeat so a lucky interleaving cannot hide it
        session_manager.sessions.clear()  # as after a restart or an eviction: only the saved file remains
        threads = 8
        barrier = threading.Barrier(threads)
        results = []

        def restore():
            try:
                barrier.wait(timeout=5)
                results.append(session_manager.get(session_id))
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)

        workers = [threading.Thread(target=restore) for _ in range(threads)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        assert not errors
        assert len(results) == threads and all(result is not None for result in results)
        assert len({id(result) for result in results}) == 1, "threads were handed different copies of one session"
        assert session_manager.sessions[session_id] is results[0]  # and it is the one kept in memory


def test_a_restore_of_an_unknown_id_is_still_none(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    assert session_manager.get("00000000-0000-0000-0000-000000000000") is None
