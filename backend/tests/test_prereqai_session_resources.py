"""Study links reach HTTP clients in plan order and shrink as concepts are marked studied."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.session import session_manager

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "examples/prerequisites/sample-paper.pdf"


def _analyze(**data):
    with SAMPLE.open("rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data=data).json()


def test_report_and_session_list_resources_in_plan_order_and_drop_studied_ones():
    body = _analyze(known="Linear Algebra")
    plan = [step["concept"] for step in body["report"]["learning_plan"]]
    assert [r["concept"] for r in body["report"]["learning_resources"]] == plan == ["Probability", "Calculus", "Neural Networks"]

    sid = body["session_id"]
    assert [r["concept"] for r in client.get(f"/api/session/{sid}").json()["next_resources"]] == plan
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Calculus"}).status_code == 200
    after = client.get(f"/api/session/{sid}").json()["next_resources"]
    assert [r["concept"] for r in after] == ["Probability", "Neural Networks"] and after[0]["url"].startswith("https://")


def test_session_without_a_report_has_no_resources_and_unknown_session_is_404():
    session_manager.sessions.clear()
    bare = session_manager.create("Bare paper")
    assert client.get(f"/api/session/{bare.session_id}").json()["next_resources"] == []
    assert client.get("/api/session/00000000-0000-4000-8000-000000000000").status_code == 404
