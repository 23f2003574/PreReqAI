"""An interrupt (Ctrl-C, SystemExit) in the middle of a session save leaves no stray temp file and keeps the last good copy."""
from pathlib import Path

import pytest

from backend.session import session_manager

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_an_interrupted_save_removes_its_temp_file_and_keeps_the_good_copy(monkeypatch, tmp_path, interrupt):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("Paper", {"a": 1})
    saved = tmp_path / f"{session.session_id}.session"
    good = saved.read_bytes()

    def interrupted(self, target):
        raise interrupt()

    session.report["a"] = 2
    with monkeypatch.context() as patched:
        patched.setattr(Path, "replace", interrupted)
        with pytest.raises(interrupt):  # the interrupt is not swallowed or turned into a failed-save flag
            session_manager.save(session)
    assert not list(tmp_path.glob("*.tmp"))
    assert saved.read_bytes() == good

    assert session_manager.save(session) is True  # the next save works
