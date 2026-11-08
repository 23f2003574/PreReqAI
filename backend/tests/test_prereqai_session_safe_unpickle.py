"""A saved session file cannot run code when loaded: only this project's own classes are restored, other globals are refused."""
import os
import pickle

from backend.session import session_manager

PROOF = "executed"


class _Malicious:
    def __reduce__(self):  # what an attacker's file would contain: a call run at load time
        return (exec, (f"import os; os.environ['{PROOF}'] = '1'",))


def test_a_malicious_pickle_is_not_executed_and_reads_as_unreadable(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    monkeypatch.delenv(PROOF, raising=False)
    session_manager.sessions.clear()
    sid = "33333333-3333-4333-8333-333333333333"
    path = tmp_path / f"{sid}.session"
    payload = pickle.dumps(_Malicious())
    path.write_bytes(payload)

    assert session_manager.get(sid) is None
    assert PROOF not in os.environ
    assert path.read_bytes() == payload  # kept for diagnosis


def test_a_system_call_payload_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    sid = "44444444-4444-4444-8444-444444444444"
    marker = tmp_path / "pwned"
    class Evil:
        def __reduce__(self):
            return (os.system, (f"touch {marker}",))
    (tmp_path / f"{sid}.session").write_bytes(pickle.dumps(Evil()))
    assert session_manager.get(sid) is None and not marker.exists()


def test_a_real_saved_session_still_restores_with_its_content(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("Paper", {"a": 1})
    session_manager.sessions.clear()
    restored = session_manager.get(session.session_id)
    assert restored is not None and restored.paper_title == "Paper" and restored.report == {"a": 1}
