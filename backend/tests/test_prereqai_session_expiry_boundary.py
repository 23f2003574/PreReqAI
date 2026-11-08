"""Expiry boundary: a saved session exactly at the maximum age is still valid; one second beyond it has expired."""
import os
import sys
from types import SimpleNamespace

import pytest

from backend.session import session_manager

NOW = 2_000_000_000.0  # fixed clock: no sleeps, no dependence on the real time
MAX_AGE_SECONDS = 2 * 86400


@pytest.mark.parametrize("extra, expired", [(-1, False), (0, False), (1, True)])
def test_session_age_against_the_maximum(tmp_path, monkeypatch, extra, expired):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.setenv("PREREQAI_SESSION_MAX_AGE_DAYS", "2")
    session = session_manager.create("t")
    path = tmp_path / f"{session.session_id}.session"
    mtime = NOW - MAX_AGE_SECONDS - extra
    os.utime(path, (mtime, mtime))
    module = sys.modules["backend.session.session_manager"]
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: NOW))
    assert module.SessionManager._expired(path) is expired
