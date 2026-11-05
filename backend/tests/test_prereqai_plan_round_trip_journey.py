"""End-to-end over the public HTTP API, with no mocks: progress made in one analysis is exported as a plan, and uploading that
plan as `resume` with the same paper in a brand-new analysis reproduces the same study state; the plan round-trips unchanged."""
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai

PAPER = Path(__file__).resolve().parents[2] / "examples" / "prerequisites" / "sample-paper.pdf"
ANALYZE = "/api/prerequisites/analyze"


def _analyze(client, **extra):
    files = {"paper": ("p.pdf", PAPER.read_bytes(), "application/pdf"), **extra.pop("files", {})}
    response = client.post(ANALYZE, files=files, data=extra)
    assert response.status_code == 200, response.text
    return response.json()


def _state(view):
    """What a learner sees of a session: its progress per concept, readiness and remaining preparation time."""
    return (view["study_progress"], view["readiness"], view["study_time"])


def test_exported_plan_resumes_the_same_state_in_a_new_analysis():
    client = TestClient(app)

    # 1. a learner analyses the paper, says what they know, and works through part of the plan
    first = _analyze(client, known=["Linear Algebra"])
    sid = first["session_id"]
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": "Probability"}).status_code == 200
    original = client.get(f"/api/session/{sid}").json()
    assert original["readiness"]["completed_concepts"] == 1
    assert [item["concept"] for item in original["study_progress"] if item["completed"]] == ["Probability"]

    # 2. the plan is exported as Markdown (the public hand-off between sessions)
    exported = client.get(f"/api/session/{sid}/plan")
    assert exported.status_code == 200 and exported.text.startswith("# Study plan:")

    # 3. a new analysis of the same paper, given only that plan, rebuilds the same state with no warnings
    resumed = _analyze(client, files={"resume": ("plan.md", exported.content, "text/markdown")})
    assert resumed["session_id"] != sid and resumed["warnings"] == []
    assert _state(client.get(f"/api/session/{resumed['session_id']}").json()) == _state(original)
    assert "Linear Algebra" not in [item["concept"] for item in original["study_progress"]]  # known stays out of the plan

    # 4. the resumed session exports exactly the same plan: the hand-off is lossless and repeatable
    again = client.get(f"/api/session/{resumed['session_id']}/plan")
    assert again.text == exported.text


def test_resuming_a_plan_does_not_touch_the_session_it_came_from():
    client = TestClient(app)
    sid = _analyze(client, known=["Linear Algebra"])["session_id"]
    exported = client.get(f"/api/session/{sid}/plan")
    before = client.get(f"/api/session/{sid}").json()
    _analyze(client, files={"resume": ("plan.md", exported.content, "text/markdown")})
    assert client.get(f"/api/session/{sid}").json() == before
