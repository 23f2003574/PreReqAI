import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform

pytestmark = pytest.mark.prereqai

client = TestClient(app, raise_server_exceptions=False)


def _session():
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]


def _fail_once(monkeypatch, attr):
    generator = getattr(platform.analysis, attr)
    real = generator.generate

    def boom(paper):
        monkeypatch.setattr(generator, "generate", real)
        raise RuntimeError("boom")

    monkeypatch.setattr(generator, "generate", boom)


def test_a_failed_known_rebuild_leaves_the_session_unchanged_and_the_retry_works(monkeypatch):
    session_id = _session()
    base = f"/api/prerequisites/sessions/{session_id}"
    client.post(f"{base}/studied", params={"concept": "Probability"})
    before = client.get(f"/api/session/{session_id}").json()

    _fail_once(monkeypatch, "study_action_generator")
    assert client.post(f"{base}/known", params={"concept": "Probability"}).status_code == 500
    assert client.get(f"/api/session/{session_id}").json() == before

    retried = client.post(f"{base}/known", params={"concept": "Probability"}).json()
    assert retried["readiness"]["total_concepts"] == before["readiness"]["total_concepts"] - 1
    assert "Probability" not in [step["concept"] for step in retried["report"]["learning_plan"]]


def test_a_failed_unmark_known_keeps_the_concept_known_and_the_retry_restores_it(monkeypatch):
    session_id = _session()
    base = f"/api/prerequisites/sessions/{session_id}"
    client.post(f"{base}/known", params={"concept": "Calculus"})
    known = client.get(f"/api/session/{session_id}").json()

    _fail_once(monkeypatch, "study_action_generator")
    assert client.delete(f"{base}/known", params={"concept": "Calculus"}).status_code == 500
    assert client.get(f"/api/session/{session_id}").json() == known

    restored = client.delete(f"{base}/known", params={"concept": "Calculus"}).json()
    assert "Calculus" in [item["concept"] for item in restored["study_progress"]]
