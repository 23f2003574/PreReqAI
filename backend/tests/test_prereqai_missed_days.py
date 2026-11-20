"""Missed-day rescheduling through the API, the saved plan file, the CLI and the page: unfinished work is moved in order, finished work is never reported or repeated, and old sessions load."""
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.cli import main as cli_main
from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.study_calendar import build_calendar, planned_steps, plan_inputs
from backend.study_plan_markdown import plan_markdown, plan_start_from_plan

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)
TODAY = date(2026, 11, 25)  # a Wednesday: the plan began on Friday the 20th


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    session = session_manager.get(platform.analyze(SAMPLE, hours_per_day=3)["session_id"])
    session.plan_start = "2026-11-20"
    session_manager.save(session)
    yield session.session_id
    session_manager.sessions.clear()


def calendar(sid, **params):
    return client.get(f"/api/session/{sid}/calendar", params={"today": TODAY.isoformat(), "weekdays": "mon,tue,wed,thu,fri", **params}).json()


def test_unfinished_work_planned_for_passed_days_is_reported_moved_and_laid_out_again_in_order(sid):
    body = calendar(sid)
    assert body["plan_start"] == "2026-11-20" and body["missed_sessions"]  # nothing was studied since the 20th
    first = body["missed_sessions"][0]
    assert first["date"] == "2026-11-20" and first["moved_to"] and first["moved_to"] >= TODAY.isoformat()
    assert all(m["date"] < TODAY.isoformat() for m in body["missed_sessions"]) and all(d["date"] >= TODAY.isoformat() for d in body["days"])
    order = lambda items: list(dict.fromkeys(items))
    assert order(m["concept"] for m in body["missed_sessions"]) == order(i["concept"] for d in body["days"] for i in d["items"])[:len(order(m["concept"] for m in body["missed_sessions"]))]  # same prerequisite order


def test_finished_work_is_not_reported_as_missed_and_is_never_scheduled_again(sid):
    before = calendar(sid)
    done = before["missed_sessions"][0]["concept"]
    assert client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": done}).status_code == 200
    after = calendar(sid)
    assert done not in {m["concept"] for m in after["missed_sessions"]} and done not in {i["concept"] for d in after["days"] for i in d["items"]} and done in after["studied"]
    assert round(sum(d["hours"] for d in after["days"]), 2) == after["remaining_hours"] < before["remaining_hours"]
    assert sum(m["hours"] for m in after["missed_sessions"]) < sum(m["hours"] for m in before["missed_sessions"])  # what was done is not missed; the rest is


def test_restarting_the_plan_clears_the_missed_list_and_an_old_session_without_a_start_still_loads(sid):
    assert calendar(sid)["missed_sessions"]
    restarted = client.post(f"/api/session/{sid}/plan-start", params={"date": TODAY.isoformat()}).json()
    assert restarted["plan_start"] == "2026-11-25" and calendar(sid)["missed_sessions"] == []
    assert client.post(f"/api/session/{sid}/plan-start", params={"date": "soon"}).status_code == 422 and client.post("/api/session/nope/plan-start").status_code == 404
    session = session_manager.get(sid)
    session.plan_start = None  # a session saved before the field existed
    session.created_at = time.mktime((2026, 11, 20, 12, 0, 0, 0, 0, 0))
    session_manager.save(session)
    session_manager.sessions.clear()
    assert client.get(f"/api/session/{sid}").json()["plan_start"] == "2026-11-20"  # its creation day
    assert calendar(sid)["plan_start"] in ("2026-11-19", "2026-11-20", "2026-11-21") and "days" in calendar(sid)


def test_the_original_schedule_comes_from_the_whole_plan_so_finished_work_does_not_shift_the_rest():
    from types import SimpleNamespace as N

    steps = [N(concept="A", estimated_hours=6), N(concept="B", estimated_hours=6), N(concept="C", estimated_hours=6)]
    # Day 1 and 2 were for A (3h a day); A was done on time. B was planned for days 3 and 4 (past), C for days 5 and 6.
    result = build_calendar([steps[1], steps[2]], {}, 3, date(2026, 11, 25), None, None, date(2026, 11, 21), ["A"], steps)
    assert {m["concept"] for m in result["missed_sessions"]} == {"B"}
    assert all(m["concept"] != "A" for m in result["missed_sessions"]) and [m["date"] for m in result["missed_sessions"] if m["concept"] == "B"] == ["2026-11-23", "2026-11-24"]
    naive = build_calendar([steps[1], steps[2]], {}, 3, date(2026, 11, 25), None, None, date(2026, 11, 21), ["A"])
    assert [m["date"] for m in naive["missed_sessions"] if m["concept"] == "B"] == ["2026-11-21", "2026-11-22"]  # without the whole plan B would be wrongly 'planned' earlier


def test_the_saved_plan_records_when_it_began_and_the_cli_reports_missed_days_on_a_resume(tmp_path, capsys):
    report = platform.analyze(SAMPLE)["report"]
    text = plan_markdown(report, "2026-11-20")
    assert "Plan started: 2026-11-20" in text and plan_start_from_plan(text) == "2026-11-20" and plan_start_from_plan(plan_markdown(report)) is None
    plan = tmp_path / "plan.md"
    plan.write_text(text, encoding="utf-8")
    long_ago = (datetime.now(timezone.utc).date() - timedelta(days=4)).isoformat()
    plan.write_text(plan_markdown(report, long_ago), encoding="utf-8")
    deadline = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
    assert cli_main(["prerequisites", "analyze", SAMPLE, "--resume", str(plan), "--deadline", deadline, "--study-days", "mon,tue,wed,thu,fri,sat,sun"]) == 0
    out = capsys.readouterr().out
    assert "calendar:" in out and "  missed: " in out and "planned for" in out and "now scheduled for" in out
    assert cli_main(["prerequisites", "analyze", SAMPLE, "--resume", str(plan), "--plan-file", str(plan)]) == 0
    assert plan_start_from_plan(plan.read_text(encoding="utf-8")) == long_ago  # an update keeps the original start
    capsys.readouterr()
    fresh = tmp_path / "fresh.md"
    assert cli_main(["prerequisites", "analyze", SAMPLE, "--plan-file", str(fresh)]) == 0
    assert plan_start_from_plan(fresh.read_text(encoding="utf-8")) == datetime.now(timezone.utc).date().isoformat()


def test_the_page_sends_the_plan_start_shows_missed_sessions_and_can_restart_the_plan():
    assert 'q.push("start="' in PAGE and "missed_sessions" in PAGE and "missedBox" in PAGE and "nothing is lost" in PAGE and "/plan-start?date=" in PAGE and 'id="restartPlan"' in PAGE
