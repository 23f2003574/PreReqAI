"""A failed session save (disk full, rename refused) leaves no half-written temp file, keeps the last good file, and a retry succeeds."""
import pickle
from pathlib import Path

from backend.session import session_manager


def _manager_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    return tmp_path


def test_failed_write_removes_the_partial_temp_file_and_a_retry_succeeds(monkeypatch, tmp_path):
    directory = _manager_dir(monkeypatch, tmp_path)
    session = session_manager.create("Paper", {"a": 1})
    saved = directory / f"{session.session_id}.session"
    good = saved.read_bytes()

    original = Path.write_bytes

    def disk_full(self, data):
        original(self, data[: len(data) // 2])  # half of it lands, then the disk fills up
        raise OSError(28, "No space left on device")

    session.report["a"] = 2
    with monkeypatch.context() as patched:
        patched.setattr(Path, "write_bytes", disk_full)
        assert session_manager.save(session) is False
    assert session_manager.last_save_ok is False
    assert not list(directory.glob("*.tmp"))  # nothing half-written is left behind
    assert saved.read_bytes() == good  # the previous good copy is intact

    assert session_manager.save(session) is True  # the retry works
    assert pickle.loads(saved.read_bytes()).report == {"a": 2}


def test_failed_rename_also_cleans_up(monkeypatch, tmp_path):
    directory = _manager_dir(monkeypatch, tmp_path)
    session = session_manager.create("Paper", {})
    monkeypatch.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(PermissionError("denied")))
    assert session_manager.save(session) is False
    assert not list(directory.glob("*.tmp"))
