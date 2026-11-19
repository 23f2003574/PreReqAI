"""Curriculum planning over several papers: deduplicated shared prerequisites, profile-aware exclusions, a deterministic explained order, one schedule, validation
and untouched sessions."""
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import curriculum, learner_profile
from backend.main import app
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)
TODAY = "2026-11-20"  # a Friday


def report(title, plan, studied=(), known=()):
    """The part of an analysis report a curriculum reads: a plan of (concept, hours), the studied concepts and the concepts marked known."""
    return {"paper": {"title": title}, "learning_plan": [{"step": i, "concept": c, "estimated_hours": h} for i, (c, h) in enumerate(plan, 1)],
            "study_progress": [{"concept": c, "completed": c in studied} for c, _ in plan],
            "missing_prerequisites": [{"concept": c, "importance": "essential", "reason": "Already known" if c in known else "needed"} for c, _ in plan]}


@pytest.fixture
def papers(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    session_manager.sessions.clear()
    made = {}
    for name, plan in {"A": [("Linear Algebra", 8), ("Probability", 6)], "B": [("Linear Algebra", 8), ("Calculus", 10)], "C": [("Probability", 6)]}.items():
        session = session_manager.create(paper_title=f"Paper {name}", report=report(f"Paper {name}", plan), paper=SimpleNamespace(pages=[]))
        made[name] = session
    yield made
    session_manager.sessions.clear()


def ids(papers, *names):
    return [papers[name].session_id for name in names]


def titles(result):
    return [paper["title"] for paper in result["papers"]]


def test_shared_prerequisites_are_studied_once_and_the_combined_workload_is_smaller(papers):
    result = curriculum.build_curriculum([papers[n] for n in "ABC"])
    assert result["hours"]["separate"] == 38 and result["hours"]["combined"] == 24 and result["hours"]["saved"] == 14 == result["hours"]["saved_by_sharing"]
    assert sorted(step["concept"] for step in result["steps"]) == ["Calculus", "Linear Algebra", "Probability"]  # each once
    shared = {item["concept"]: item for item in result["shared_prerequisites"]}
    assert set(shared) == {"Linear Algebra", "Probability"} and set(shared["Linear Algebra"]["papers"]) == {"Paper A", "Paper B"} and "studied once" in shared["Linear Algebra"]["reason"]


def test_the_paper_order_is_by_extra_prerequisite_hours_deterministic_and_explained(papers):
    result = curriculum.build_curriculum([papers[n] for n in "ABC"])
    assert titles(result) == ["Paper C", "Paper A", "Paper B"]  # 6 h, then 8 h more (Probability is already scheduled), then 10 h
    assert [p["extra_hours"] for p in result["papers"]] == [6, 8, 10]
    assert "shares Probability" in result["papers"][1]["reason"] and "shares Linear Algebra" in result["papers"][2]["reason"] and "not repeated" in result["papers"][2]["reason"]
    assert titles(curriculum.build_curriculum([papers[n] for n in "CBA"])) == titles(result)  # the order of the request does not matter


def test_the_learner_profile_and_studied_concepts_remove_unnecessary_work(papers):
    profile = {"known": ["Linear Algebra"], "studied": [], "quiz": {}}
    result = curriculum.build_curriculum([papers[n] for n in "ABC"], profile)
    assert {e["concept"]: e["reason"] for e in result["excluded"]} == {"Linear Algebra": "known in your learner profile"}
    assert result["hours"]["combined"] == 16 and result["hours"]["saved_by_mastery"] == 16 and "Linear Algebra" not in [s["concept"] for s in result["steps"]]
    papers["C"].report["study_progress"] = [{"concept": "Probability", "completed": True}]  # studied in its own session
    again = curriculum.build_curriculum([papers[n] for n in "ABC"], profile)
    assert "Probability" not in [s["concept"] for s in again["steps"]] and again["hours"]["combined"] == 10
    assert titles(again) == ["Paper A", "Paper C", "Paper B"]  # A and C have nothing left (equal cost: by title), then B
    assert all("nothing is left to study" in again["papers"][i]["reason"] for i in (0, 1))


def test_one_schedule_follows_the_deadline_and_weekdays(papers):
    result = curriculum.build_curriculum([papers[n] for n in "ABC"], None, date(2026, 11, 20), date(2026, 12, 31), 3.0, {0, 1, 2, 3, 4})
    days = result["calendar"]["days"]
    assert round(sum(d["hours"] for d in days), 2) == 24 and result["calendar"]["feasibility"]["status"] == "achievable"
    assert [i["concept"] for d in days for i in d["items"]][0] == "Probability" and all(date.fromisoformat(d["date"]).weekday() < 5 for d in days)
    tight = curriculum.build_curriculum([papers[n] for n in "ABC"], None, date(2026, 11, 20), date(2026, 11, 24), 3.0)
    assert tight["calendar"]["feasibility"]["status"] == "infeasible" and tight["calendar"]["feasibility"]["additional_daily_hours"] > 0


def test_the_sessions_are_only_read(papers):
    before = {sid: deepcopy((s.report, s.quiz_attempts, s.quiz_pending, s.paper_title)) for sid, s in ((p.session_id, p) for p in papers.values())}
    curriculum.build_curriculum([papers[n] for n in "ABC"], {"known": ["Calculus"], "studied": [], "quiz": {}}, date(2026, 11, 20), None, 3.0)
    response = client.post("/api/curriculum", json={"session_ids": ids(papers, "A", "B"), "today": TODAY})
    assert response.status_code == 200
    assert {sid: (s.report, s.quiz_attempts, s.quiz_pending, s.paper_title) for sid, s in ((p.session_id, p) for p in papers.values())} == before


def test_the_api_builds_a_curriculum_with_a_profile_and_a_deadline(papers, tmp_path):
    learner_profile.save(tmp_path / "profiles" / "me.json", ["Calculus"], [])
    body = client.post("/api/curriculum", json={"session_ids": ids(papers, "A", "B", "C"), "profile": "me", "deadline": "2026-11-25", "hours_per_day": 4,
                                                "weekdays": "mon,tue,wed,thu,fri", "today": TODAY}).json()
    assert body["status"] == "success" and body["hours"]["combined"] == 14 and [e["concept"] for e in body["excluded"]] == ["Calculus"]
    assert body["calendar"]["feasibility"]["status"] == "achievable" and body["calendar"]["daily_hours"] == 4 and body["calendar"]["finish_date"] == "2026-11-25"
    assert [p["position"] for p in body["papers"]] == [1, 2, 3]
    ignored = client.post("/api/curriculum", json={"session_ids": ids(papers, "A", "B"), "profile": "me"})
    assert ignored.json()["status"] == "success"


def test_invalid_requests_get_useful_errors(papers, tmp_path, monkeypatch):
    post = lambda **body: client.post("/api/curriculum", json=body)
    assert post(session_ids=ids(papers, "A")).status_code == 422 and "2 to 10" in post(session_ids=[]).json()["detail"]
    assert post(session_ids=ids(papers, "A", "A")).status_code == 422
    missing = post(session_ids=[papers["A"].session_id, "nope", "gone"])
    assert missing.status_code == 404 and "nope, gone" in missing.json()["detail"]
    assert post(session_ids=ids(papers, "A", "B"), profile="../x").status_code == 422
    (tmp_path / "profiles").mkdir(exist_ok=True)
    (tmp_path / "profiles" / "bad.json").write_text("{nope", encoding="utf-8")
    assert post(session_ids=ids(papers, "A", "B"), profile="bad").status_code == 409 and (tmp_path / "profiles" / "bad.json").read_text() == "{nope"
    assert post(session_ids=ids(papers, "A", "B"), deadline="soon").status_code == 422
    assert post(session_ids=ids(papers, "A", "B"), hours_per_day=99).status_code == 422
    assert post(session_ids=ids(papers, "A", "B"), weekdays="xyz").status_code == 422
    monkeypatch.delenv("PREREQAI_PROFILE_DIR")
    assert "ignored" in post(session_ids=ids(papers, "A", "B"), profile="me").json()["warnings"][0]
    assert client.post("/api/curriculum", json={"session_ids": "x"}).status_code == 422  # not a list


def test_the_page_can_build_a_curriculum_from_the_ticked_analyses():
    assert 'id="curriculumBtn"' in PAGE and "/api/curriculum" in PAGE and "planCurriculum" in PAGE and 'className = "pick"' in PAGE
