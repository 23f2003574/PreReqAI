"""Saved sessions in PREREQAI_SESSION_DIR expire after PREREQAI_SESSION_MAX_AGE_DAYS (default 30)."""
import os
import time

from backend.session import session_manager


def _age(path, days):
    old = time.time() - days * 86400
    os.utime(path, (old, old))


def test_creating_a_session_purges_expired_files_but_keeps_recent_ones(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    old, recent = session_manager.create("old"), session_manager.create("recent")
    _age(tmp_path / f"{old.session_id}.session", 31)
    _age(tmp_path / f"{recent.session_id}.session", 29)
    (tmp_path / "leftover.tmp").write_bytes(b"x")
    _age(tmp_path / "leftover.tmp", 40)

    monkeypatch.setattr(session_manager, "_last_purge", float("-inf"))  # the sweep is throttled; this create is the first after the interval

    session_manager.create("new")

    names = {p.name for p in tmp_path.iterdir()}
    assert f"{old.session_id}.session" not in names and "leftover.tmp" not in names
    assert f"{recent.session_id}.session" in names and len(names) == 2


def test_an_expired_session_is_unknown_after_a_restart_and_its_file_is_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("t")
    path = tmp_path / f"{session.session_id}.session"
    _age(path, 45)
    session_manager.sessions.clear()
    assert session_manager.get(session.session_id) is None and not path.exists()


def test_max_age_is_configurable_zero_keeps_forever_and_bad_values_use_the_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("t")
    path = tmp_path / f"{session.session_id}.session"
    _age(path, 400)

    monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", "0")
    assert session_manager.purge_expired() == 0 and path.exists()

    for bad in ("soon", "-5", "nan"):  # unusable settings never disable or shorten expiry unexpectedly
        monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", bad)
        assert session_manager._max_age_seconds() == 30 * 86400

    monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", "500")
    assert session_manager.purge_expired() == 0 and path.exists()
    monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", "7")
    assert session_manager.purge_expired() == 1 and not path.exists()


def test_creating_sessions_sweeps_the_directory_at_most_once_per_interval(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(session_manager, "_last_purge", float("-inf"))
    sweeps = []
    real = session_manager.purge_expired
    monkeypatch.setattr(session_manager, "purge_expired", lambda: sweeps.append(1) or real())

    first, second = session_manager.create("a"), session_manager.create("b")
    assert len(sweeps) == 1
    _age(tmp_path / f"{first.session_id}.session", 45)
    session_manager.sessions.clear()
    assert session_manager.get(first.session_id) is None  # still never served once expired, swept or not

    monkeypatch.setattr(session_manager, "_last_purge", time.time() - session_manager.PURGE_INTERVAL_SECONDS)
    session_manager.create("c")
    assert len(sweeps) == 2 and second.session_id
