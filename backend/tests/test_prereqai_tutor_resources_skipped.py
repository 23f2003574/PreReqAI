"""Asking where to study a prerequisite that needs no study says why, instead of listing other concepts' resources."""
from starlette.testclient import TestClient

from backend.main import app


def _ask(question, extra):
    client = TestClient(app)
    with open("examples/prerequisites/sample-paper.pdf", "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=extra).json()["session_id"]
    return client.post(f"/api/session/{sid}/question", json={"question": question}).json()["responses"][0]["answer"]


def test_known_concept_explains_it_is_not_in_the_plan():
    answer = _ask("Where can I study linear algebra?", {"known": "Linear Algebra"})
    assert answer.startswith("Linear Algebra is not in your study plan")
    assert "Already known" in answer and "Calculus" not in answer


def test_planned_concept_and_generic_questions_are_unchanged():
    assert _ask("Where can I study calculus?", {"known": "Linear Algebra"}).startswith("Suggested resources: Calculus: MIT 18.01")
    generic = _ask("Which resources should I use?", {"known": "Linear Algebra"})
    assert generic.startswith("Suggested resources: Probability") and "Linear Algebra" not in generic
