"""When a progress change cannot be written to PREREQAI_SESSION_DIR, the response says so instead of reporting a silent success."""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _analyze():
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]


def _url(sid, kind):
    return f"/api/prerequisites/sessions/{sid}/{kind}"


def test_every_progress_endpoint_warns_when_the_change_cannot_be_saved(tmp_path, monkeypatch):
    sid = _analyze()  # created with no session directory configured
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(blocker))  # saving now fails: the "directory" is a file

    calls = [client.post(_url(sid, "studied"), params={"concept": "Probability"}),
             client.delete(_url(sid, "studied"), params={"concept": "Probability"}),
             client.post(_url(sid, "known"), params={"concept": "Calculus"}),
             client.delete(_url(sid, "known"), params={"concept": "Calculus"})]
    for response in calls:
        body = response.json()
        assert response.status_code == 200 and body["status"] == "success"
        assert len(body["warnings"]) == 1 and "will not survive a server restart" in body["warnings"][0]


def test_no_warning_when_saving_works_or_is_not_configured(tmp_path, monkeypatch):
    sid = _analyze()
    assert "warnings" not in client.post(_url(sid, "studied"), params={"concept": "Probability"}).json()

    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    sid = _analyze()
    assert "warnings" not in client.post(_url(sid, "known"), params={"concept": "Calculus"}).json()
