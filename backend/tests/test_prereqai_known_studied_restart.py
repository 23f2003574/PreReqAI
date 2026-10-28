"""Studied-then-known progress and the time left survive a server restart, and un-marking known after the restart restores both."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai

client = TestClient(app)


def _restart():
    session_manager.sessions.clear()  # a new server process: only the saved files remain
    session_manager._last_used.clear()


def _url(sid, kind):
    return f"/api/prerequisites/sessions/{sid}/{kind}"


def test_un_marking_known_after_a_restart_restores_the_studied_concept_and_the_hours(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        body = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()
    sid, report = body["session_id"], body["report"]
    hours = {step["concept"]: step["estimated_hours"] for step in report["learning_plan"]}
    total = report["study_time"]["total_hours"]

    client.post(_url(sid, "studied"), params={"concept": "Probability"})
    client.post(_url(sid, "known"), params={"concept": "Probability"})
    _restart()

    after = client.get(f"/api/session/{sid}").json()
    assert "Probability" not in [item["concept"] for item in after["study_progress"]]
    assert after["study_time"]["remaining_hours"] == total - hours["Probability"]

    restored = client.delete(_url(sid, "known"), params={"concept": "Probability"}).json()
    assert {item["concept"] for item in restored["study_progress"] if item["completed"]} == {"Probability"}
    assert restored["study_time"]["total_hours"] == total
    assert restored["study_time"]["remaining_hours"] == total - hours["Probability"]


def test_un_marking_known_a_concept_that_was_never_studied_leaves_nothing_completed(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    client.post(_url(sid, "known"), params={"concept": "Calculus"})
    _restart()
    restored = client.delete(_url(sid, "known"), params={"concept": "Calculus"}).json()
    assert not any(item["completed"] for item in restored["study_progress"])
    assert restored["study_time"]["remaining_hours"] == restored["study_time"]["total_hours"]
