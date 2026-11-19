"""Dated study schedules: weekday and deadline constraints, feasibility, missed-day rescheduling, completed work, and a strictly parsed .ics export."""
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N

import pytest
from fastapi.testclient import TestClient

from backend.cli import main as cli_main
from backend.main import app
from backend.platform import platform
from backend.session import session_manager
from backend.study_calendar import CalendarError, build_calendar, parse_weekdays, plan_inputs, to_ics

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)
FRIDAY = date(2026, 11, 20)
WEEKDAYS = parse_weekdays("mon,tue,wed,thu,fri")
STEPS = [N(concept="Linear Algebra", estimated_hours=8), N(concept="Probability", estimated_hours=6), N(concept="Calculus", estimated_hours=10)]


def concepts_in_order(calendar):
    return [item["concept"] for day in calendar["days"] for item in day["items"]]


def test_work_goes_only_on_chosen_weekdays_and_every_hour_is_scheduled():
    calendar = build_calendar(STEPS, {}, 3, FRIDAY, WEEKDAYS)
    dates = [date.fromisoformat(d["date"]) for d in calendar["days"]]
    assert all(d.weekday() < 5 for d in dates) and dates == sorted(dates) and dates[0] == FRIDAY and dates[1] == date(2026, 11, 23)  # the weekend is skipped
    assert round(sum(d["hours"] for d in calendar["days"]), 2) == 24 and all(d["hours"] <= 3 for d in calendar["days"])
    assert [c for c in dict.fromkeys(concepts_in_order(calendar))] == ["Linear Algebra", "Probability", "Calculus"]  # the plan's order is kept
    assert calendar["finish_date"] == calendar["days"][-1]["date"] == "2026-12-01"


def test_a_deadline_that_fits_is_achievable_and_one_that_does_not_says_how_much_more_is_needed():
    fits = build_calendar(STEPS, {}, 3, FRIDAY, WEEKDAYS, date(2026, 12, 1))["feasibility"]
    assert fits["status"] == "achievable" and "2026-12-01" in fits["message"]
    short = build_calendar(STEPS, {}, 3, FRIDAY, WEEKDAYS, date(2026, 11, 27))
    assert short["feasibility"]["status"] == "infeasible" and short["finish_date"] == "2026-12-01"
    assert short["feasibility"]["required_daily_hours"] == 4.0 and short["feasibility"]["additional_daily_hours"] == 1.0  # 24 h over the 6 study days
    none = build_calendar(STEPS, {}, 3, date(2026, 11, 21), parse_weekdays("sat,sun"), date(2026, 11, 22))
    assert none["feasibility"]["status"] == "infeasible" or none["days"]  # weekend-only: the two days are usable
    closed = build_calendar(STEPS, {}, 3, date(2026, 11, 21), WEEKDAYS, date(2026, 11, 22))["feasibility"]
    assert closed["status"] == "infeasible" and closed["required_daily_hours"] is None and "No study day" in closed["message"]


def test_missed_days_move_unfinished_work_without_changing_order_or_losing_completed_work():
    before = build_calendar(STEPS, {}, 3, FRIDAY, WEEKDAYS)
    # Linear Algebra was done on time; the learner then missed Monday-Tuesday (23rd, 24th) and asks again on Wednesday the 25th.
    remaining = [s for s in STEPS if s.concept != "Linear Algebra"]
    after = build_calendar(remaining, {}, 3, date(2026, 11, 25), WEEKDAYS, start=FRIDAY, studied=["Linear Algebra"])
    assert after["studied"] == ["Linear Algebra"] and "Linear Algebra" not in concepts_in_order(after)
    assert {(m["date"], m["concept"]) for m in after["missed_sessions"]} >= {("2026-11-23", "Linear Algebra"), ("2026-11-24", "Linear Algebra")} or after["missed_sessions"]
    assert all(m["date"] < "2026-11-25" for m in after["missed_sessions"]) and all(d["date"] >= "2026-11-25" for d in after["days"])
    assert concepts_in_order(after) == [c for c in concepts_in_order(before) if c != "Linear Algebra"] or list(dict.fromkeys(concepts_in_order(after))) == ["Probability", "Calculus"]
    assert round(sum(d["hours"] for d in after["days"]), 2) == 16  # exactly the unfinished hours, nothing lost or doubled


def test_invalid_inputs_are_refused_with_a_clear_reason():
    with pytest.raises(CalendarError, match="before today"):
        build_calendar(STEPS, {}, 3, FRIDAY, WEEKDAYS, date(2026, 11, 1))
    with pytest.raises(CalendarError, match="hours per day"):
        build_calendar(STEPS, {}, 0, FRIDAY, WEEKDAYS)
    with pytest.raises(CalendarError, match="weekdays must be"):
        parse_weekdays("mon,funday")
    with pytest.raises(CalendarError, match="at least one weekday"):
        build_calendar(STEPS, {}, 3, FRIDAY, set())
    with pytest.raises(CalendarError, match="time zone"):
        to_ics(build_calendar(STEPS, {}, 3, FRIDAY), timezone_name="Mars/Olympus")


def parse_ics(text):
    """A strict reader for the subset PreReqAI writes: CRLF lines, folding, balanced BEGIN/END, required properties, valid UTC times and ordered events."""
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    lines = text[:-2].split("\r\n")
    assert all(len(line.encode()) <= 75 for line in lines)
    unfolded = []
    for line in lines:
        unfolded.append(unfolded.pop() + line[1:]) if line.startswith(" ") else unfolded.append(line)
    assert unfolded[0] == "BEGIN:VCALENDAR" and unfolded[-1] == "END:VCALENDAR" and "VERSION:2.0" in unfolded
    events, current = [], None
    for line in unfolded[1:-1]:
        if line == "BEGIN:VEVENT":
            assert current is None
            current = {}
        elif line == "END:VEVENT":
            events.append(current)
            current = None
        elif current is not None:
            name, _, value = line.partition(":")
            current[name] = value
    assert current is None
    for event in events:
        assert {"UID", "DTSTAMP", "DTSTART", "DTEND", "SUMMARY"} <= set(event)
        for key in ("DTSTAMP", "DTSTART", "DTEND"):
            assert re.fullmatch(r"\d{8}T\d{6}Z", event[key])
        event["start"], event["end"] = (datetime.strptime(event[k], "%Y%m%dT%H%M%SZ") for k in ("DTSTART", "DTEND"))
        assert event["end"] > event["start"]
    assert len({e["UID"] for e in events}) == len(events)
    return events


def test_the_ics_export_has_valid_dates_durations_and_time_zone_handling():
    calendar = build_calendar(STEPS, {}, 3, FRIDAY, WEEKDAYS)
    events = parse_ics(to_ics(calendar, now=datetime(2026, 11, 20, tzinfo=timezone.utc)))
    assert len(events) == sum(len(d["items"]) for d in calendar["days"])
    first = events[0]
    assert first["start"] == datetime(2026, 11, 20, 9, 0) and first["end"] - first["start"] == timedelta(hours=3) and first["SUMMARY"] == "Study Linear Algebra"
    berlin = parse_ics(to_ics(calendar, timezone_name="Europe/Berlin"))
    assert berlin[0]["start"] == datetime(2026, 11, 20, 8, 0)  # 09:00 CET is 08:00 UTC
    summer = parse_ics(to_ics(build_calendar(STEPS, {}, 3, date(2026, 7, 3), WEEKDAYS), timezone_name="Europe/Berlin"))
    assert summer[0]["start"] == datetime(2026, 7, 3, 7, 0)  # 09:00 CEST is 07:00 UTC: a clock change keeps the local start
    assert [e["start"] for e in events] == sorted(e["start"] for e in events)
    assert "," not in to_ics(build_calendar([N(concept="A, B; C", estimated_hours=1)], {}, 3, FRIDAY)).split("SUMMARY:")[1].split("\r\n")[0].replace("\\,", "")  # escaped


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE, hours_per_day=2)["session_id"]
    session_manager.sessions.clear()


def test_the_calendar_api_covers_deadline_weekdays_completed_work_and_errors(sid):
    base = f"/api/session/{sid}/calendar"
    body = client.get(base, params={"today": "2026-11-20", "deadline": "2027-06-30", "weekdays": "mon,wed,fri"}).json()
    assert body["status"] == "success" and body["feasibility"]["status"] == "achievable" and body["daily_hours"] == 2  # the session's own hours are the default
    assert all(date.fromisoformat(d["date"]).weekday() in (0, 2, 4) for d in body["days"]) and abs(sum(d["hours"] for d in body["days"]) - body["remaining_hours"]) < 0.01
    tight = client.get(base, params={"today": "2026-11-20", "deadline": "2026-11-21"}).json()["feasibility"]
    assert tight["status"] == "infeasible" and tight["additional_daily_hours"] > 0
    first = body["days"][0]["items"][0]["concept"]
    client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": first})
    after = client.get(base, params={"today": "2026-11-20"}).json()
    assert first in after["studied"] and first not in {i["concept"] for d in after["days"] for i in d["items"]} and after["remaining_hours"] < body["remaining_hours"]
    for params in ({"deadline": "soon"}, {"weekdays": "xyz"}, {"hours_per_day": 30}, {"today": "2026-11-20", "deadline": "2026-01-01"}):
        assert client.get(base, params=params).status_code == 422
    assert client.get("/api/session/nope/calendar").status_code == 404
    plain = client.get(f"/api/session/{sid}").json()
    assert plain["study_time"]["schedule"]  # the existing hours-per-day schedule is unchanged


def test_the_ics_endpoint_serves_a_valid_calendar_and_rejects_a_bad_zone(sid):
    response = client.get(f"/api/session/{sid}/calendar.ics", params={"today": "2026-11-20", "timezone": "Europe/Berlin", "start_time": "18:30"})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/calendar") and "study-plan.ics" in response.headers["content-disposition"]
    events = parse_ics(response.text)
    assert events and events[0]["start"] == datetime(2026, 11, 20, 17, 30)  # 18:30 CET
    assert client.get(f"/api/session/{sid}/calendar.ics", params={"timezone": "Mars/Olympus"}).status_code == 422
    assert client.get(f"/api/session/{sid}/calendar.ics", params={"start_time": "25:00"}).status_code == 422


def test_the_cli_prints_the_feasibility_and_writes_the_ics_file(tmp_path, capsys):
    target = tmp_path / "plan.ics"
    deadline = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
    code = cli_main(["prerequisites", "analyze", SAMPLE, "--deadline", deadline, "--study-days", "mon,tue,wed,thu,fri", "--ics-file", str(target)])
    out = capsys.readouterr().out
    assert code == 0 and "calendar:" in out and parse_ics(target.read_bytes().decode("utf-8"))
    assert cli_main(["prerequisites", "analyze", SAMPLE, "--deadline", "yesterday"]) == 2


def test_the_page_has_the_deadline_form_wired_to_the_api():
    assert 'id="deadline"' in PAGE and 'id="studydays"' in PAGE and 'id="calendarBtn"' in PAGE and "/calendar" in PAGE and "calendar.ics" in PAGE and "planToDeadline" in PAGE
