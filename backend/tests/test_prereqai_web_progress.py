"""The web page tracks study progress through the existing session endpoints: what it calls, what it reads back, and that a reload restores it."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def studied(sid, concept, method="post"):
    return getattr(client, method)(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": concept})


def test_the_page_calls_the_existing_progress_endpoints_and_guards_against_duplicate_requests():
    for fragment in ('"/api/prerequisites/sessions/"', '"/studied"', '"/known"', '"POST"', '"DELETE"', '"/api/session/"', '"/plan"',
                     "prereqai.session", "if (state.busy) return;", "tick.disabled = state.busy", "known.disabled = state.busy", "study-plan.md"):
        assert fragment in PAGE, fragment
    assert "innerHTML" not in PAGE and "https://" not in PAGE.replace("https://arxiv.org/abs/1706.03762", "")  # still no foreign loads or HTML injection


def test_the_fields_the_page_reads_back_after_a_tick_exist(sid):
    body = studied(sid, "Probability").json()
    assert body["status"] == "success" and {"study_progress", "readiness", "study_time"} <= set(body)
    assert {"concept", "completed"} <= set(body["study_progress"][0]) and {"status", "progress_percent"} <= set(body["readiness"])
    assert {"total_hours", "recommended_days"} <= set(body["study_time"])


def test_the_fields_the_page_reads_after_marking_known_exist(sid):
    body = client.post(f"/api/prerequisites/sessions/{sid}/known", params={"concept": "Calculus"}).json()
    report = body["report"]
    assert {"step", "concept", "estimated_hours"} <= set(report["learning_plan"][0]) and "Calculus" not in [s["concept"] for s in report["learning_plan"]]
    assert [p["concept"] for p in report["missing_prerequisites"] if p["status"] == "known"] == ["Calculus"]
    undone = client.delete(f"/api/prerequisites/sessions/{sid}/known", params={"concept": "Calculus"}).json()
    assert "Calculus" in [s["concept"] for s in undone["report"]["learning_plan"]]


def test_a_reload_restores_progress_and_readiness_from_the_session(sid):
    before = client.get(f"/api/session/{sid}").json()["readiness"]["progress_percent"]
    assert studied(sid, "Probability").status_code == 200
    session_manager.sessions.clear()  # a server restart: only the saved file remains
    restored = client.get(f"/api/session/{sid}").json()  # what the page's restore() reads
    assert restored["paper_title"] and restored["readiness"]["progress_percent"] > before
    assert {p["concept"]: p["completed"] for p in restored["study_progress"]}["Probability"] is True
    hours = {}
    for day in restored["study_time"]["schedule"]:  # the page rebuilds each step's hours from the schedule
        for item in day["items"]:
            hours[item["concept"]] = hours.get(item["concept"], 0) + item["hours"]
    assert set(hours) == {p["concept"] for p in restored["study_progress"]}
    assert all(r["url"].startswith("https://") for r in restored["next_resources"]) and "Probability" not in [r["concept"] for r in restored["next_resources"]]


def test_the_downloaded_plan_carries_the_progress(sid):
    studied(sid, "Probability")
    plan = client.get(f"/api/session/{sid}/plan")
    assert plan.status_code == 200 and plan.headers["content-type"].startswith("text/markdown") and "- [x] 2. Probability" in plan.text


def test_failures_have_the_detail_and_hint_the_page_shows(sid):
    unknown_concept = studied(sid, "Quantum Gravity")
    assert unknown_concept.status_code == 422 and unknown_concept.json()["detail"] and unknown_concept.json()["hint"]
    missing = client.post("/api/prerequisites/sessions/nope/studied", params={"concept": "Probability"})
    assert missing.status_code == 404 and missing.json()["detail"]
    assert client.get("/api/session/nope").status_code == 404 and client.get("/api/session/nope/plan").status_code == 404
    assert client.get(f"/api/session/{sid}").json()["readiness"]["completed_concepts"] == 0  # a refused request changed nothing


def test_ticking_twice_and_unticking_are_safe(sid):
    assert studied(sid, "Probability").status_code == 200 and studied(sid, "Probability").status_code == 200
    assert studied(sid, "Probability", "delete").status_code == 200
    assert client.get(f"/api/session/{sid}").json()["readiness"]["completed_concepts"] == 0
