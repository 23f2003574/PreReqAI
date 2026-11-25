"""Persisted mastery informs suggestions in other papers' sessions and curriculum hints, but only the learner's choice removes anything."""
from types import SimpleNamespace
from pathlib import Path

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend import learner_profile
from backend.main import app
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PREREQAI_PROFILE_DIR", str(tmp_path / "profiles"))
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


def analyse(profile="me"):
    with open(SAMPLE, "rb") as handle:
        return client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}, data={"profile": profile}).json()["session_id"]


def master(env, concept="Probability"):
    """Two different questions answered correctly twice each, checked by the system (assessed), saved in the profile the way the diagnostic saves them."""
    path = env / "profiles" / "me.json"
    for number in (1, 2):
        for day in (2, 0):  # answered on two different days: one sitting is not durable mastery (backend/mastery_model.py)
            learner_profile.record_quiz(path, f"{concept}:{number}", concept, "knew", moment=datetime.now(timezone.utc) - timedelta(days=day, minutes=-number), graded={"correct": True, "confidence": "medium"})
    assert concept in learner_profile.mastered(learner_profile.load_full(path)[0]["quiz"])


def suggestions(sid):
    return client.get(f"/api/session/{sid}").json()["suggest_known"]


def test_a_concept_mastered_in_one_paper_is_suggested_as_known_in_another_with_the_reason(env):
    first = analyse()
    assert suggestions(first) == []
    master(env)
    second = analyse()  # another paper session of the same learner
    [suggestion] = [s for s in suggestions(second) if s["concept"] == "Probability"]
    assert suggestion["source"] == "profile" and "earlier sessions" in suggestion["reason"] and "mastered" in suggestion["reason"] and suggestion["distinct_questions"] == 2
    still = client.get(f"/api/session/{second}").json()
    assert "Probability" in [item["concept"] for item in still["study_progress"]] and not next(i for i in still["study_progress"] if i["concept"] == "Probability")["completed"]  # offered, not applied
    assert any(s["concept"] == "Probability" for s in suggestions(first))  # the older session sees it too, now that the profile holds it


def test_the_learner_can_decline_and_restore_a_suggestion_and_accepting_uses_the_known_endpoint(env):
    master(env)
    sid = analyse()
    declined = client.post(f"/api/session/{sid}/suggestions/dismiss", params={"concept": "probability"}).json()
    assert declined["dismissed"] is True and not [s for s in declined["suggest_known"] if s["concept"] == "Probability"]
    assert not [s for s in suggestions(sid) if s["concept"] == "Probability"]
    session_manager.sessions.clear()  # a restart keeps the decision
    assert not [s for s in suggestions(sid) if s["concept"] == "Probability"]
    restored = client.delete(f"/api/session/{sid}/suggestions/dismiss", params={"concept": "Probability"}).json()
    assert [s for s in restored["suggest_known"] if s["concept"] == "Probability"]
    assert client.post(f"/api/session/{sid}/suggestions/dismiss", params={"concept": "Astrology"}).status_code == 422
    assert client.post(f"/api/prerequisites/sessions/{sid}/known", params={"concept": "Probability"}).status_code == 200
    assert not [s for s in suggestions(sid) if s["concept"] == "Probability"]  # a known concept is not in the plan, so it is not suggested again


def test_a_profile_free_session_and_an_unreadable_profile_give_no_profile_suggestions(env, monkeypatch):
    master(env)
    (env / "profiles" / "broken.json").write_text("{nope", encoding="utf-8")
    assert not [s for s in suggestions(analyse("broken")) if s["source"] == "profile"]
    monkeypatch.delenv("PREREQAI_PROFILE_DIR")
    session_manager.sessions.clear()
    assert suggestions(platform.analyze(SAMPLE)["session_id"]) == []


def paper(title, plan):
    report = {"paper": {"title": title}, "learning_plan": [{"step": i, "concept": c, "estimated_hours": h} for i, (c, h) in enumerate(plan, 1)],
              "study_progress": [{"concept": c, "completed": False} for c, _ in plan], "missing_prerequisites": [{"concept": c, "importance": "essential", "reason": "needed"} for c, _ in plan]}
    return session_manager.create(paper_title=title, report=report, paper=SimpleNamespace(pages=[]))


def test_curriculum_hints_mastered_concepts_and_leaves_them_out_only_when_the_learner_accepts(env):
    master(env)
    a, b = paper("A", [("Linear Algebra", 8), ("Probability", 6)]), paper("B", [("Probability", 6), ("Calculus", 10)])
    ids = [a.session_id, b.session_id]
    plain = client.post("/api/curriculum", json={"session_ids": ids, "profile": "me", "today": "2026-11-20"}).json()
    assert [h["concept"] for h in plain["mastery_hints"]] == ["Probability"] and "until you accept" in plain["mastery_hints"][0]["reason"]
    assert plain["hours"]["combined"] == 24 and "Probability" in [s["concept"] for s in plain["steps"]]  # a hint changes nothing by itself
    accepted = client.post("/api/curriculum", json={"session_ids": ids, "profile": "me", "today": "2026-11-20", "accept_mastered": ["Probability", "Calculus"]}).json()
    assert accepted["hours"]["combined"] == 18 and "Probability" not in [s["concept"] for s in accepted["steps"]]
    assert [e["concept"] for e in accepted["excluded"]] == ["Probability"] and "you accepted" in accepted["excluded"][0]["reason"] and "Calculus" in [s["concept"] for s in accepted["steps"]]  # not mastered: stays
    assert not client.post("/api/curriculum", json={"session_ids": ids, "today": "2026-11-20"}).json()["mastery_hints"]  # no profile, no hints


def test_suggestions_and_curriculum_agree_on_what_is_mastered(env):
    master(env, "Calculus")
    quiz = learner_profile.load_full(env / "profiles" / "me.json")[0]["quiz"]
    assert set(learner_profile.mastered(quiz)) == {"Calculus"}
    sid = analyse()
    assert {s["concept"] for s in suggestions(sid) if s["source"] == "profile"} == {"Calculus"}
    pair = [paper("A", [("Calculus", 10)]), paper("B", [("Probability", 6)])]
    hints = client.post("/api/curriculum", json={"session_ids": [p.session_id for p in pair], "profile": "me", "today": "2026-11-20"}).json()["mastery_hints"]
    assert [h["concept"] for h in hints] == ["Calculus"]


def test_the_page_declines_on_the_server_and_lets_the_learner_tick_what_to_leave_out():
    assert "/suggestions/dismiss?concept=" in PAGE and "accept_mastered" in PAGE and "mastery_hints" in PAGE and "Leave it out" in PAGE
