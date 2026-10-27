"""'How long will <concept> take?' is answered with that concept's planned hours, not its definition or the whole plan's total."""
from starlette.testclient import TestClient

from backend.main import app


def _session(extra=None):
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=extra or {}).json()["session_id"]
    return client, sid


def _ask(client, sid, question):
    return client.post(f"/api/session/{sid}/question", json={"question": question}).json()["responses"][0]["answer"]


def test_hours_for_a_named_planned_concept():
    client, sid = _session()
    assert _ask(client, sid, "How long will calculus take?") == "Calculus: about 10 hours of study."
    assert _ask(client, sid, "How many hours is neural networks?") == "Neural Networks: about 15 hours of study."


def test_a_studied_concept_says_so():
    client, sid = _session({"studied": "Probability"})
    assert _ask(client, sid, "How long does probability take?") == "Probability: about 10 hours of study. You have already studied it."


def test_whole_plan_time_and_known_concepts_are_unchanged():
    client, sid = _session({"known": "Calculus"})
    assert _ask(client, sid, "How long will it take to prepare?").startswith("Plan about 37 hours")
    assert not _ask(client, sid, "How long will calculus take?").endswith("hours of study.")  # known: not in the plan
