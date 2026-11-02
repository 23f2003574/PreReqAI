"""Concurrent saves of one session (requests run in threads) all succeed and leave a readable file and no temp files."""
import threading

from backend.session import session_manager


def test_concurrent_saves_of_one_session_do_not_fail_or_corrupt_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("Concurrent", {"padding": "x" * 1_000_000})
    results = []

    def save_often():
        for _ in range(25):
            results.append(session_manager.save(session))

    threads = [threading.Thread(target=save_often) for _ in range(6)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]

    assert results == [True] * 150
    assert list(tmp_path.glob("*.tmp")) == []
    session_manager.sessions.pop(session.session_id)
    assert session_manager.get(session.session_id).paper_title == "Concurrent"
