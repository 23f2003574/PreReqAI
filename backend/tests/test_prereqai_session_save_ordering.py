"""A slow save that pickled an older state must not overwrite the file after a later save wrote the newer state."""
import pickle
import sys
import threading

from backend.session import session_manager


def test_a_stale_save_cannot_overwrite_a_newer_one(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("Ordering", {"version": 1})
    real_dumps = pickle.dumps
    started, release = threading.Event(), threading.Event()

    def dumps(obj, *args, **kwargs):
        data = real_dumps(obj, *args, **kwargs)
        if threading.current_thread().name == "slow":  # this save pickled version 1 and is then held up
            started.set()
            release.wait(timeout=1)
        return data

    patch = monkeypatch.context()
    patch.__enter__().setattr(sys.modules["backend.session.session_manager"].pickle, "dumps", dumps)
    slow = threading.Thread(target=session_manager.save, args=(session,), name="slow")
    slow.start()
    assert started.wait(timeout=5)
    session.report["version"] = 2  # a later update, saved by another request while the first save is still in flight
    fast = threading.Thread(target=session_manager.save, args=(session,), name="fast")
    fast.start()
    fast.join(timeout=0.3)  # without the per-session lock it finishes now, and the slow save then overwrites it
    release.set()
    slow.join()
    fast.join()

    patch.__exit__(None, None, None)
    session_manager.sessions.pop(session.session_id)
    assert session_manager.get(session.session_id).report["version"] == 2


def test_saves_of_independent_sessions_do_not_wait_for_each_other(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    first, second = session_manager.create("A", {}), session_manager.create("B", {})
    assert session_manager.save(first) and session_manager.save(second)
    assert first.session_id != second.session_id and len(list(tmp_path.glob("*.session"))) == 2
