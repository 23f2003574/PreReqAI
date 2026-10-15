"""A saved session file that cannot be read is reported as such and can be cleared, not shown as a plain 404."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)
BAD = "11111111-1111-4111-8111-111111111111"


def test_unreadable_saved_session_is_explained_and_delete_clears_it(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    (tmp_path / f"{BAD}.session").write_bytes(b"garbage")

    for response in (client.get(f"/api/session/{BAD}"),
                     client.post(f"/api/session/{BAD}/question", json={"question": "What is attention?"})):
        assert response.status_code == 404
        assert response.json()["detail"] == "Session could not be restored"
        assert "DELETE /api/session/" + BAD in response.json()["hint"]

    deleted = client.delete(f"/api/session/{BAD}")
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert not (tmp_path / f"{BAD}.session").exists()
    assert client.get(f"/api/session/{BAD}").json()["detail"] == "Session not found"


def test_truly_unknown_and_healthy_sessions_behave_as_before(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    other = "22222222-2222-4222-8222-222222222222"
    assert client.get(f"/api/session/{other}").json()["detail"] == "Session not found"
    assert client.delete(f"/api/session/{other}").status_code == 404
    live = session_manager.create("Healthy paper")
    assert client.get(f"/api/session/{live.session_id}").status_code == 200
    assert client.delete(f"/api/session/{live.session_id}").status_code == 200
