"""GET /api/session lists known sessions, including ones saved by a previous server run."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)


def test_list_returns_sessions_newest_first_including_saved_ones_after_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    first = session_manager.create("First paper", report={"readiness": {"status": "Ready to Read"}})
    second = session_manager.create("Second paper")
    first.created_at, second.created_at = 100.0, 200.0
    session_manager.save(first), session_manager.save(second)
    session_manager.sessions.clear()  # restart: only the files remain

    body = client.get("/api/session").json()
    assert body["status"] == "success"
    assert [s["paper_title"] for s in body["sessions"]] == ["Second paper", "First paper"]
    assert body["sessions"][1]["readiness"] == "Ready to Read" and body["sessions"][0]["readiness"] is None


def test_list_skips_bad_files_expired_and_deleted_sessions_and_is_empty_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    (tmp_path / "not-a-uuid.session").write_bytes(b"x")
    corrupt = "11111111-1111-4111-8111-111111111111"
    (tmp_path / f"{corrupt}.session").write_bytes(b"not a pickle")
    kept, gone = session_manager.create("Kept"), session_manager.create("Gone")
    client.delete(f"/api/session/{gone.session_id}")

    assert [s["session_id"] for s in client.get("/api/session").json()["sessions"]] == [kept.session_id]

    monkeypatch.delenv("PREREQAI_SESSION_DIR")
    session_manager.sessions.clear()
    assert client.get("/api/session").json()["sessions"] == []
