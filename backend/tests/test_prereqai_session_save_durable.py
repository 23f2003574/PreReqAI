"""A session file is flushed to disk (fsync) before the atomic replacement, and a failed sync leaves the last good file intact."""
import os
from pathlib import Path

from backend.session import session_manager


def test_the_temp_file_is_synced_before_it_replaces_the_session_file(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("Paper", {"a": 1})
    events = []
    real_fsync, real_replace = os.fsync, Path.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (events.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(Path, "replace", lambda self, target: (events.append("replace"), real_replace(self, target))[1])

    session.report["a"] = 2
    assert session_manager.save(session) is True
    assert events == ["fsync", "replace"]


def test_a_failed_sync_keeps_the_last_good_file_and_leaves_no_temp_file(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("Paper", {"a": 1})
    saved = tmp_path / f"{session.session_id}.session"
    good = saved.read_bytes()

    def failing(fd):
        raise OSError(5, "Input/output error")

    session.report["a"] = 2
    with monkeypatch.context() as patched:
        patched.setattr(os, "fsync", failing)
        assert session_manager.save(session) is False
    assert saved.read_bytes() == good and not list(tmp_path.glob("*.tmp"))
    assert session_manager.save(session) is True
