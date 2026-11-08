"""Truncated or structurally invalid saved sessions fail safely, say what happened, and are left on disk for diagnosis."""
import pickle

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)


def _saved(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    session = session_manager.create("Valid paper")
    path = tmp_path / f"{session.session_id}.session"
    assert path.is_file()
    session_manager.sessions.clear()
    return session.session_id, path


@pytest.mark.parametrize("damage", [
    lambda data: data[: len(data) // 2],          # truncated mid-write
    lambda data: pickle.dumps({"not": "a session"}),  # valid pickle, wrong structure
    lambda data: pickle.dumps(["session"]),
])
def test_damaged_files_are_reported_and_preserved(tmp_path, monkeypatch, damage):
    session_id, path = _saved(tmp_path, monkeypatch)
    damaged = damage(path.read_bytes())
    path.write_bytes(damaged)

    response = client.get(f"/api/session/{session_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Session could not be restored"
    assert f"DELETE /api/session/{session_id}" in response.json()["hint"]
    assert path.read_bytes() == damaged  # not deleted or rewritten: kept for diagnosis


def test_a_damaged_file_does_not_stop_a_valid_one_from_restoring(tmp_path, monkeypatch):
    bad_id, bad_path = _saved(tmp_path, monkeypatch)
    bad_path.write_bytes(bad_path.read_bytes()[:10])
    good = session_manager.create("Good paper")
    session_manager.sessions.clear()
    assert client.get(f"/api/session/{bad_id}").status_code == 404
    assert client.get(f"/api/session/{good.session_id}").status_code == 200
