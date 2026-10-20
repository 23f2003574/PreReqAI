"""A concept marked known by mistake can be put back into the study plan."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform

SAMPLE = "examples/prerequisites/sample-paper.pdf"
client = TestClient(app)


def _plan(report):
    return [(step["concept"], step["estimated_hours"]) for step in report["learning_plan"]]


def test_unmarking_known_restores_the_original_plan_resources_and_time():
    original = platform.analyze(SAMPLE)
    sid = platform.analyze(SAMPLE)["session_id"]
    platform.mark_concept_known(sid, "Calculus")
    restored = platform.unmark_concept_known(sid, "calculus")
    assert _plan(restored) == _plan(original["report"])
    assert restored["study_time"] == original["report"]["study_time"]
    assert restored["learning_resources"] == original["report"]["learning_resources"]
    assert restored["readiness"] == original["report"]["readiness"]
    assert restored["study_progress"] == original["report"]["study_progress"]


def test_other_known_concepts_and_studied_progress_survive_the_undo():
    sid = platform.analyze(SAMPLE, known=["Calculus", "Probability"])["session_id"]
    platform.mark_concept_studied(sid, "Neural Networks")
    report = platform.unmark_concept_known(sid, "Calculus")
    assert [name for name, _ in _plan(report)] == ["Linear Algebra", "Calculus", "Neural Networks"]  # Probability stays known
    assert {s["concept"] for s in report["study_progress"] if s["completed"]} == {"Neural Networks"}
    assert platform.mark_concept_known(sid, "Calculus")["learning_plan"][-1]["concept"] == "Neural Networks"  # and it can be marked again


def test_http_undo_answers_success_then_422_for_a_concept_not_marked_known():
    with open(SAMPLE, "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    base = f"/api/prerequisites/sessions/{sid}/known?concept=Probability"
    assert client.post(base).status_code == 200
    undone = client.delete(base)
    assert undone.status_code == 200 and "Probability" in [s["concept"] for s in undone.json()["study_progress"]]
    again = client.delete(base)
    assert again.status_code == 422 and "not marked as known" in again.json()["detail"]
    assert client.delete("/api/prerequisites/sessions/nope/known?concept=Probability").status_code == 404
