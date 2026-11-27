import pytest

from backend import adaptive_plan
from backend.prerequisites.prerequisite_paths import KNOWN_REASON

pytestmark = pytest.mark.prereqai


def _report():
    return {"learning_plan": [{"concept": "Calculus", "estimated_hours": 10}], "math_plan": [], "study_progress": [],
            "missing_prerequisites": [{"concept": "Linear Algebra", "reason": KNOWN_REASON, "importance": "essential"}, {"concept": "Calculus", "reason": "Requires external study", "importance": "essential"}]}


def _misses(n=3, confidence="high"):
    return [{"question_id": f"Linear Algebra:{i}", "concept": "Linear Algebra", "graded": True, "correct": False, "confidence": confidence, "outcome": "missed", "at": f"2026-11-0{i}T10:00:00Z"} for i in range(1, n + 1)]


def test_confident_misses_reinstate_a_known_subject():
    result = adaptive_plan.propose(_report(), _misses())
    found = [a for a in result["adjustments"] if a["concept"] == "Linear Algebra"]
    assert found and found[0]["action"] == "reinstate" and found[0]["adjusted_hours"] > 0
    assert any(p["concept"] == "Linear Algebra" and p["hours"] > 0 for p in result["plan"])


def test_the_stored_report_and_known_list_are_not_changed():
    report = _report()
    adaptive_plan.propose(report, _misses())
    assert report["missing_prerequisites"][0]["reason"] == KNOWN_REASON


def test_reject_override_keeps_the_claim():
    result = adaptive_plan.propose(_report(), _misses(), {"Linear Algebra": "reject"})
    found = [a for a in result["adjustments"] if a["concept"] == "Linear Algebra"][0]
    assert found["overridden"] and found["adjusted_hours"] == 0.0


def test_too_little_evidence_changes_nothing():
    result = adaptive_plan.propose(_report(), _misses(1, "low"))
    assert not [a for a in result["adjustments"] if a["concept"] == "Linear Algebra"]


def test_the_adapted_report_schedules_the_reinstated_subject():
    adapted = adaptive_plan.adapted_report(_report(), _misses())
    assert any(s["concept"] == "Linear Algebra" and s.get("reinstated") for s in adapted["learning_plan"])


def test_api_reinstates_and_asks_a_verification_question(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app, base_url="http://localhost")
    pdf = open("examples/prerequisites/sample-paper.pdf", "rb").read()
    sid = client.post("/api/prerequisites/analyze", files={"paper": ("x.pdf", pdf, "application/pdf")}, data={"known": ["Linear Algebra"]}).json()["session_id"]
    asked = [q["concept"] for q in client.get(f"/api/session/{sid}/adaptive-plan/assessment?limit=12").json()["questions"]]
    assert "Linear Algebra" in asked
    for _ in range(3):
        q = client.get(f"/api/session/{sid}/diagnostic/question?concept=Linear Algebra").json()
        right = __import__("backend.tutor.quiz_session", fromlist=["x"])._lookup(q["question_id"])[2]["answer"]
        wrong = next(i for i, o in enumerate(q["options"]) if o != right)
        client.post(f"/api/session/{sid}/diagnostic/answer", json={"question_id": q["question_id"], "choice": wrong, "confidence": "high"})
    actions = {a["concept"]: a["action"] for a in client.get(f"/api/session/{sid}/adaptive-plan").json()["adjustments"]}
    assert actions.get("Linear Algebra") == "reinstate"
