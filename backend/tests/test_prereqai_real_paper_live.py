"""Release blocker check (docs/release-checklist.md): PreReqAI run end to end on a real published paper.

Opt-in because it downloads from arXiv:  PREREQAI_LIVE_PAPER=1 python -m pytest backend/tests/test_prereqai_real_paper_live.py
Skipped otherwise, so CI and offline runs are unaffected. The assertions are deliberately limited to what must hold for any
analysed paper plus the concepts "Attention Is All You Need" (arXiv:1706.03762) certainly discusses; a failure here is the
real-paper finding the checklist asks for."""
import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform

pytestmark = [
    pytest.mark.skipif(os.environ.get("PREREQAI_LIVE_PAPER") != "1", reason="live arXiv run: set PREREQAI_LIVE_PAPER=1"),
]

SOURCE = "arXiv:1706.03762"


def _check_report(report):
    names = {c["concept"] for c in report["concept_evidence"]}
    assert {"Attention", "Transformer"} <= names and len(names) >= 5, sorted(names)
    plan = report["learning_plan"]
    assert plan and [step["step"] for step in plan] == list(range(1, len(plan) + 1))
    assert all(step["estimated_hours"] > 0 for step in plan)
    assert report["study_time"]["total_hours"] == sum(step["estimated_hours"] for step in plan)
    assert report["readiness"]["total_concepts"] == len(plan)
    assert report["paper"]["title"] not in ("", "Unknown Title") and report["paper"]["pages"] >= 1
    return names


def test_a_real_published_paper_is_analysed_end_to_end_over_the_platform_and_http():
    outcome = platform.analyze(SOURCE, diagnostics=True)
    assert outcome["status"] == "success", outcome
    names = _check_report(outcome["report"])

    client = TestClient(app)
    response = client.post("/api/prerequisites/analyze", data={"source": SOURCE})
    assert response.status_code == 200
    body = response.json()
    assert _check_report(body["report"]) == names  # CLI/platform and HTTP agree on the same paper

    asked = client.post(f"/api/session/{body['session_id']}/question", json={"question": "What should I learn first?"})
    assert asked.status_code == 200
    assert "Study these in order" in asked.json()["responses"][0]["answer"]
