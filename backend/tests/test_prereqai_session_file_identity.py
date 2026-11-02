"""A saved session file only loads under the id it was saved for, so a renamed or copied file cannot impersonate
(or later overwrite) another session."""
import shutil
import uuid

from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

PAPER = "examples/prerequisites/sample-paper.pdf"


def test_a_session_file_copied_under_another_id_is_not_restored_as_that_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    client = TestClient(app)
    with open(PAPER, "rb") as pdf:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", pdf, "application/pdf")}).json()["session_id"]
    other = str(uuid.uuid4())
    shutil.copy(tmp_path / f"{sid}.session", tmp_path / f"{other}.session")
    session_manager.sessions.clear()

    assert client.get(f"/api/session/{other}").status_code == 404
    assert other not in session_manager.sessions
    assert other not in [item["session_id"] for item in client.get("/api/session").json()["sessions"]]
    assert session_manager.is_unreadable(other)

    # the genuine session is untouched and still restores
    assert client.get(f"/api/session/{sid}").status_code == 200
    assert (tmp_path / f"{sid}.session").is_file()
