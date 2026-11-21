"""Graded spaced repetition: again/hard/good/easy with a per-question ease, a daily review cap that a long absence cannot break, reviews in the calendar and its .ics, and old review records kept."""
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend import learner_profile, spaced_review, study_calendar

pytestmark = pytest.mark.prereqai
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


def run(grades, difficulty="Medium"):
    entry, moment, waits = None, T0, []
    for grade in grades:
        entry = spaced_review.graded_update(entry, "Softmax", grade, moment, difficulty)
        waits.append(entry["interval_hours"])
        moment = spaced_review.parse_time(entry["due"])
    return entry, waits


def test_grades_change_the_interval_and_the_questions_own_ease():
    good, good_waits = run(["good", "good", "good", "good"])
    hard, hard_waits = run(["good", "good", "hard", "hard"])
    easy, easy_waits = run(["good", "good", "easy", "easy"])
    assert good_waits[:2] == [24.0, 72.0] and good_waits[2] > 72 and hard_waits[3] < good_waits[3] < easy_waits[3]
    assert hard["ease"] < good["ease"] <= 2.5 < easy["ease"] and all(e["last_outcome"] == "knew" for e in (good, hard, easy))
    again, _ = run(["good", "good", "again"])
    assert again["streak"] == 0 and again["interval_hours"] == 4.0 and again["last_outcome"] == "missed" and again["ease"] < 2.5 and again["missed"] == 1 and again["knew"] == 2


def test_a_harder_question_grows_its_interval_more_slowly_and_ease_stays_in_bounds():
    _, hard_q = run(["good"] * 6, "Hard")
    _, easy_q = run(["good"] * 6, "Easy")
    assert hard_q[-1] < easy_q[-1] and max(easy_q) <= 365 * 24
    floor, _ = run(["again"] * 30)
    ceiling, _ = run(["good"] + ["easy"] * 30)
    assert floor["ease"] == spaced_review.MIN_EASE and ceiling["ease"] == spaced_review.MAX_EASE and ceiling["interval_hours"] <= 365 * 24
    with pytest.raises(ValueError, match="again, hard, good, easy"):
        spaced_review.graded_update(None, "Softmax", "perfect", T0)


def items(count, due="2026-10-01T09:00:00Z"):
    return [{"question_id": f"Softmax:{i}", "concept": "Softmax", "due": due} for i in range(count)]


def test_a_long_absence_becomes_capped_days_not_one_huge_day_and_nothing_is_lost_or_duplicated():
    plan = spaced_review.schedule(items(95), date(2026, 11, 20), cap=10, horizon_days=30)
    assert all(day["count"] <= 10 for day in plan["days"]) and sum(d["count"] for d in plan["days"]) + len(plan["deferred"]) == 95
    assert plan["days"][0]["date"] == "2026-11-20" and plan["backlog_days"] == 10 and plan["deferred"] == []
    ids = [i["question_id"] for d in plan["days"] for i in d["items"]]
    assert len(ids) == len(set(ids)) == 95
    capped = spaced_review.schedule(items(500), date(2026, 11, 20), cap=5, horizon_days=30)
    assert max(d["count"] for d in capped["days"]) == 5 and len(capped["deferred"]) == 500 - 5 * 31 and capped["days"][-1]["date"] == "2026-12-20"


def test_a_30_day_simulation_of_daily_reviews_never_exceeds_the_cap():
    cap, quiz, today, per_day = 6, {}, date(2026, 11, 1), []
    for i in range(40):  # forty questions, all learned on day 0
        quiz[f"Softmax:{i + 1}"] = spaced_review.graded_update(None, "Softmax", "good", T0)
    for day in range(30):
        moment = datetime.combine(today + timedelta(days=day), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=8)
        queue = spaced_review.queue(quiz, moment, upcoming_limit=100)
        plan = spaced_review.schedule([*queue["due"], *queue["upcoming"]], today + timedelta(days=day), cap, 30)
        todays = next((d for d in plan["days"] if d["date"] == (today + timedelta(days=day)).isoformat()), {"items": [], "count": 0})
        per_day.append(todays["count"])
        for item in todays["items"]:  # the learner does today's reviews, grading them alternately good and hard
            quiz[item["question_id"]] = spaced_review.graded_update(quiz[item["question_id"]], "Softmax", "good" if day % 2 else "hard", moment)
    assert max(per_day) <= cap and sum(per_day) > 40  # reviews kept recurring, never above the cap


def test_a_zero_or_invalid_cap_is_refused():
    for bad in (0, -1, True, 2.5):
        with pytest.raises(ValueError, match="at least 1"):
            spaced_review.schedule(items(1), date(2026, 11, 20), cap=bad)


def test_reviews_appear_in_the_calendar_and_the_ics_export():
    steps = [SimpleNamespace(concept="Probability", estimated_hours=2.0)]
    calendar = study_calendar.build_calendar(steps, {}, 2.0, date(2026, 11, 20), None, None)
    plan = spaced_review.schedule(items(3, "2026-11-20T08:00:00Z"), date(2026, 11, 20), cap=2)
    study_calendar.add_reviews(calendar, plan)
    assert [r["count"] for r in calendar["reviews"]] == [2, 1] and calendar["review_cap"] == 2 and calendar["reviews"][0]["concepts"] == ["Softmax"]
    ics = study_calendar.to_ics(calendar, now=datetime(2026, 11, 20, tzinfo=timezone.utc))
    assert ics.count("BEGIN:VEVENT") == 1 + 2 and "SUMMARY:Review 2 questions" in ics and "SUMMARY:Review 1 question\r\n" in ics and "SUMMARY:Study Probability" in ics
    assert "DTSTART:20261120T110000Z" in ics  # the first day's reviews follow its two hours of study


def test_old_review_records_load_unchanged_and_gain_ease_when_graded_and_invalid_ease_is_rejected(tmp_path):
    path = tmp_path / "p.json"
    old = {"concept": "Softmax", "attempts": 3, "knew": 2, "missed": 1, "streak": 2, "last_outcome": "knew", "first_seen": "2026-11-01T00:00:00Z", "last_seen": "2026-11-05T00:00:00Z",
           "interval_hours": 72.0, "due": "2026-11-08T00:00:00Z"}
    path.write_text(json.dumps({"format": learner_profile.FORMAT, "schema_version": 2, "known": [], "studied": [], "quiz": {"Softmax:1": old}}), encoding="utf-8")
    assert learner_profile.load_full(path)[0]["quiz"]["Softmax:1"] == old
    entry = learner_profile.record_review(path, "Softmax:1", "Softmax", "easy", moment=T0)
    saved = json.loads(path.read_text())["quiz"]["Softmax:1"]
    assert saved["attempts"] == 4 and saved["knew"] == 3 and saved["missed"] == 1 and saved["first_seen"] == old["first_seen"] and saved["last_grade"] == "easy" and 2.5 < saved["ease"] <= 2.65 and entry == saved
    bad = json.dumps({"format": learner_profile.FORMAT, "schema_version": 2, "known": [], "studied": [], "quiz": {"Softmax:1": {**old, "ease": 9, "last_grade": "good"}}}).encode()
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.parse_full(bad)
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.record_review(path, "Softmax:1", "Softmax", "perfect")
    with pytest.raises(learner_profile.ProfileError):
        learner_profile.record_review(path, "Nope:1", "Nonexistent Concept", "good")


def test_review_schedule_reads_the_profile_and_caps_each_day(tmp_path):
    path = tmp_path / "p.json"
    for i in range(1, 26):
        learner_profile.record_review(path, f"Softmax:{i}", "Softmax", "good", moment=T0 - timedelta(days=30))
    plan, problem = learner_profile.review_schedule(path, date(2026, 11, 20), cap=10)
    assert problem == "" and [d["count"] for d in plan["days"]] == [10, 10, 5]
