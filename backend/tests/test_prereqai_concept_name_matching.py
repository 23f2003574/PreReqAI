"""Concept names match the same way everywhere: --known/--studied and the session endpoints ignore case, spacing, hyphens and
underscores, as the tutor does for names in questions ("linear-algebra" is "Linear Algebra")."""
from starlette.testclient import TestClient

from backend.main import app
from backend.platform import platform

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def test_known_and_studied_accept_hyphen_and_underscore_spellings():
    outcome = platform.analyze(SAMPLE, known=["linear-algebra"], studied=["neural_networks", "PROBABILITY"])
    report = outcome["report"]
    assert outcome["warnings"] == []
    assert "Linear Algebra" not in [step["concept"] for step in report["learning_plan"]]
    assert {item["concept"]: item["completed"] for item in report["study_progress"]} == {
        "Probability": True, "Calculus": False, "Neural Networks": True}


def test_session_endpoints_accept_the_same_spellings():
    client = TestClient(app)
    with open(SAMPLE, "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    base = f"/api/prerequisites/sessions/{sid}"
    assert client.post(base + "/studied", params={"concept": "neural-networks"}).status_code == 200
    assert client.post(base + "/known", params={"concept": "Linear_Algebra"}).status_code == 200
    assert client.delete(base + "/known", params={"concept": "linear-algebra"}).status_code == 200
    assert client.delete(base + "/studied", params={"concept": "neural_networks"}).status_code == 200
    progress = {i["concept"]: i["completed"] for i in client.get(f"/api/session/{sid}").json()["study_progress"]}
    assert progress["Linear Algebra"] is False and progress["Neural Networks"] is False
