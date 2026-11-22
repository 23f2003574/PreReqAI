"""Spaced reviews are part of the day's hours: study room shrinks by the review time, feasibility counts it, and a day never holds more than the configured hours."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from backend import spaced_review, study_calendar as sc

pytestmark = pytest.mark.prereqai
TODAY = date(2026, 12, 1)


def steps(hours):
    return [SimpleNamespace(concept="Calculus", estimated_hours=hours)]


def schedule(per_day, days=3, cap=100):
    items = [{"question_id": f"q{d}-{i}", "concept": "Calculus", "due": (TODAY + timedelta(days=d)).isoformat() + "T08:00:00Z"} for d in range(days) for i in range(per_day)]
    return spaced_review.schedule(items, TODAY, cap=cap)


def test_without_reviews_the_calendar_is_unchanged():
    assert sc.build_calendar(steps(7), {}, 2.0, TODAY) == sc.build_calendar(steps(7), {}, 2.0, TODAY, reserved=None) == sc.build_calendar(steps(7), {}, 2.0, TODAY, reserved={})


def test_review_time_is_deducted_from_each_days_study_room():
    reviews = schedule(40)  # 40 reviews x 1.5 min = 1 h a day
    reserved = sc.review_hours(reviews)
    calendar = sc.build_calendar(steps(5), {}, 2.0, TODAY, reserved=reserved)
    assert [d["hours"] for d in calendar["days"][:3]] == [1.0, 1.0, 1.0] and calendar["finish_date"] == (TODAY + timedelta(days=3)).isoformat()
    sc.add_reviews(calendar, reviews)
    for row in calendar["workload"]:
        assert row["total_hours"] <= row["limit_hours"] + 1e-9 and row["review_minutes"] == 60.0


def test_a_tight_deadline_becomes_infeasible_with_reviews_and_the_extra_hours_are_explained():
    deadline = TODAY + timedelta(days=2)  # three days of 2 h hold the 6 h of study only without reviews
    plain = sc.build_calendar(steps(6), {}, 2.0, TODAY, deadline=deadline)
    assert plain["feasibility"]["status"] == "achievable"
    reserved = sc.review_hours(schedule(40))
    busy = sc.build_calendar(steps(6), {}, 2.0, TODAY, deadline=deadline, reserved=reserved)["feasibility"]
    assert busy["status"] == "infeasible" and busy["additional_daily_hours"] == pytest.approx(1.0, abs=0.01) and busy["required_daily_hours"] == pytest.approx(3.0, abs=0.01)
    assert "Spaced reviews take" in busy["message"]


def test_a_day_with_only_reviews_holds_no_study():
    reserved = {TODAY.isoformat(): 2.0}  # the whole day
    calendar = sc.build_calendar(steps(1), {}, 2.0, TODAY, reserved=reserved)
    assert calendar["days"][0]["date"] == (TODAY + timedelta(days=1)).isoformat()


def test_minutes_per_review_is_configurable_and_shown_in_the_calendar_and_ics():
    reviews = schedule(10, days=1)
    calendar = sc.build_calendar(steps(2), {}, 2.0, TODAY, reserved=sc.review_hours(reviews, 3.0))
    sc.add_reviews(calendar, reviews, 3.0)
    assert calendar["minutes_per_review"] == 3.0 and calendar["reviews"][0]["minutes"] == 30.0 and calendar["workload"][0]["total_hours"] == 2.0
    assert "about 30 min" in sc.to_ics(calendar, title="t")
