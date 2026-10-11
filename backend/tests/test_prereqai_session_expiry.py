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
