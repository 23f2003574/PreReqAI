"""A saved file that unpickles to something other than a session must not break the session API."""
import pickle

from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app, raise_server_exceptions=False)
FOREIGN = "33333333-3333-4333-8333-333333333333"


def test_a_readable_but_foreign_file_is_unknown_and_does_not_break_the_listing(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    (tmp_path / f"{FOREIGN}.session").write_bytes(pickle.dumps({"old": "format"}))
    good = session_manager.create("Good paper")
    session_manager.sessions.clear()  # restart: only the files remain

    listing = client.get("/api/session")
    assert listing.status_code == 200
    assert [s["session_id"] for s in listing.json()["sessions"]] == [good.session_id]
    for response in (
        client.get(f"/api/session/{FOREIGN}"),
        client.post(f"/api/session/{FOREIGN}/question", json={"question": "hi"}),
    ):
        assert response.status_code == 404
    assert client.post(f"/api/prerequisites/sessions/{FOREIGN}/studied?concept=Calculus").status_code == 404


def test_a_valid_saved_session_still_restores_after_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    saved = session_manager.create("Kept paper")
    session_manager.sessions.clear()

    response = client.get(f"/api/session/{saved.session_id}")
    assert response.status_code == 200 and response.json()["paper_title"] == "Kept paper"
