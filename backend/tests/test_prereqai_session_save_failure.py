"""A configured but unwritable PREREQAI_SESSION_DIR is reported instead of silently losing persistence."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


def _upload():
    return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", SAMPLE.read_bytes(), "application/pdf")}).json()


def test_an_unwritable_session_dir_still_analyses_but_warns_it_will_not_survive_a_restart(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(blocker / "sessions"))

    body = _upload()

    assert body["status"] == "success" and body["session_id"]
    assert any("could not be saved" in warning and "PREREQAI_SESSION_DIR" in warning for warning in body["warnings"])
    assert client.get(f"/api/session/{body['session_id']}").status_code == 200  # memory stays authoritative


def test_a_writable_or_unset_session_dir_adds_no_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    assert not any("could not be saved" in w for w in _upload()["warnings"])
    assert (tmp_path / "sessions").is_dir()
    monkeypatch.delenv("PREREQAI_SESSION_DIR")
    assert not any("could not be saved" in w for w in _upload()["warnings"])
