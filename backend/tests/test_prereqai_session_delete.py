"""DELETE /api/session/{id} removes a session from memory and from PREREQAI_SESSION_DIR."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)


def test_deleting_a_session_removes_it_from_memory_and_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("t")
    saved = tmp_path / f"{session.session_id}.session"
    assert saved.exists()

    response = client.delete(f"/api/session/{session.session_id}")
    assert response.status_code == 200 and response.json()["deleted"] is True
    assert not saved.exists() and session.session_id not in session_manager.sessions
    assert client.get(f"/api/session/{session.session_id}").status_code == 404


def test_a_persisted_session_not_in_memory_can_be_deleted_and_a_second_delete_is_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session = session_manager.create("t")
    session_manager.sessions.clear()  # after a restart only the file remains

    assert client.delete(f"/api/session/{session.session_id}").status_code == 200
    assert not list(tmp_path.iterdir())
    assert client.delete(f"/api/session/{session.session_id}").status_code == 404


def test_malformed_ids_are_404_and_touch_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    (tmp_path / "secret.session").write_bytes(b"x")
    for bad in ("secret", "..%2Fsecret", "nope"):
        assert client.delete(f"/api/session/{bad}").status_code == 404
    assert (tmp_path / "secret.session").exists()
