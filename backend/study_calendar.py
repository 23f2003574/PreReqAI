"""Deadline-aware study calendars: the remaining plan laid out on real dates, whether it fits before a deadline, rescheduling of missed days, and an
iCalendar (.ics) export.

Work is placed on the learner's available weekdays, `hours_per_day` hours a day, in the plan's own schedule order (essential prerequisites first, never
before something they depend on), so the order never changes whatever happens to the dates. Studied concepts are not scheduled again. A learner who
missed days asks again with `today` set: the work planned for earlier available days that is not done is reported as moved, and everything still to do is
laid out again from `today` on. Dates are ISO (YYYY-MM-DD). Without a deadline the calendar only says when the work would end."""
import hashlib
import math
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

from backend.prerequisites.study_time_estimator import schedule_order

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_DAYS = 3650  # ten years: a schedule that would run longer is reported as not ending
_EPS = 1e-9


class CalendarError(ValueError):
    """An input that cannot be scheduled; the message says what to change."""


def parse_date(value, label):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise CalendarError(f"{label} must be a date like 2026-12-31, not {value!r}") from None


def parse_weekdays(value):
    """The set of weekday numbers (Monday is 0) from 'mon,tue,fri' (names of three letters or more) or None for every day; CalendarError for anything else."""
    if value in (None, ""):
        return set(range(7))
    names = [part.strip().lower()[:3] for part in str(value).replace(" ", ",").split(",") if part.strip()]
    if not names or any(name not in WEEKDAYS for name in names):
        raise CalendarError(f"weekdays must be names such as mon,tue,wed (from {', '.join(WEEKDAYS)}), not {value!r}")
    return {WEEKDAYS.index(name) for name in names}


def planned_steps(report):
    """Every step of the report's plan, studied or not, in plan order (what the original schedule was made of)."""
    return [SimpleNamespace(concept=step["concept"], estimated_hours=step["estimated_hours"]) for step in report.get("learning_plan", [])]


def plan_inputs(report):
    """(remaining steps, importance, studied concepts) from an analysis report: the plan's steps not yet studied, in plan order."""
    done = {item["concept"] for item in report.get("study_progress", []) if item.get("completed")}
    steps = [SimpleNamespace(concept=step["concept"], estimated_hours=step["estimated_hours"]) for step in report.get("learning_plan", [])]
    importance = {item["concept"]: item.get("importance") for item in report.get("missing_prerequisites", [])}
    return [step for step in steps if step.concept not in done], importance, sorted(done)


def _lay_out(steps, importance, daily_hours, weekdays, first_day, limit):
    """([{date, weekday, hours, items}], finish date or None) placing the steps on available days from `first_day`, at most `limit` days ahead."""
    days, items, room, day = [], [], daily_hours, first_day
    queue = [[step.concept, float(step.estimated_hours)] for step in schedule_order(steps, importance)]

    def close():
        nonlocal items, room
        if items:
            days.append({"date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()], "hours": round(sum(i["hours"] for i in items), 2), "items": items})
        items, room = [], daily_hours

    for offset in range(limit):
        day = first_day + timedelta(days=offset)
        if not queue:
            break
        if day.weekday() not in weekdays:
            continue
        while queue and room > _EPS:
            concept, left = queue[0]
            take = min(left, room)
            items.append({"concept": concept, "hours": round(take, 2)})
            room -= take
            queue[0][1] -= take
            if queue[0][1] <= _EPS:
                queue.pop(0)
        close()
    return days, (date.fromisoformat(days[-1]["date"]) if days and not queue else None)


def build_calendar(steps, importance, daily_hours, today, weekdays=None, deadline=None, start=None, studied=(), planned=None):
    """The dated schedule and its assessment (see the module description). `steps` are the plan's steps still to study (objects with `concept` and
    `estimated_hours`), `today` the first day work can happen, `start` (default `today`) the day the plan began, used only to report missed sessions. `planned` (default `steps`)
    is the whole plan including what is already studied: the original schedule is laid out from it, so work finished on time is not reported as missed and the days the unfinished
    work was planned for are the days it really had."""
    weekdays = weekdays if weekdays is not None else set(range(7))
    if isinstance(daily_hours, bool) or not isinstance(daily_hours, (int, float)) or not math.isfinite(daily_hours) or not 0 < daily_hours <= 24:
        raise CalendarError("hours per day must be above 0 and at most 24")
    if not weekdays:
        raise CalendarError("choose at least one weekday to study on")
    start = start or today
    if start > today:
        raise CalendarError("the plan cannot start after today")
    if deadline is not None and deadline < today:
        raise CalendarError(f"the deadline {deadline.isoformat()} is before today ({today.isoformat()})")
    remaining = sum(step.estimated_hours for step in steps)
    days, finish = _lay_out(steps, importance, daily_hours, weekdays, today, MAX_DAYS)
    moved = []
    if start < today:  # what the original plan put on the days that have passed and is still not done
        original, _ = _lay_out(planned if planned is not None else steps, importance, daily_hours, weekdays, start, (today - start).days)
        finished = set(studied)
        later = {}
        for day in days:
            for item in day["items"]:
                later.setdefault(item["concept"], day["date"])
        moved = [{"date": day["date"], "concept": item["concept"], "hours": item["hours"], "moved_to": later.get(item["concept"])}
                 for day in original for item in day["items"] if item["concept"] not in finished]
    result = {"today": today.isoformat(), "remaining_hours": round(remaining, 2), "daily_hours": daily_hours, "weekdays": [WEEKDAYS[i] for i in sorted(weekdays)],
              "studied": list(studied), "missed_sessions": moved, "days": days, "finish_date": finish.isoformat() if finish else None}
    if deadline is None or not remaining:
        result["feasibility"] = {"deadline": deadline.isoformat() if deadline else None, "status": "achievable",
                                 "message": "Nothing is left to study." if not remaining else "No deadline was set."}
        return result
    usable = sum(1 for offset in range((deadline - today).days + 1) if (today + timedelta(days=offset)).weekday() in weekdays)
    fits = finish is not None and finish <= deadline
    if fits:
        feasibility = {"status": "achievable", "message": f"The remaining {result['remaining_hours']} h fit before {deadline.isoformat()}: you finish on {finish.isoformat()}."}
    elif usable == 0:
        feasibility = {"status": "infeasible", "required_daily_hours": None, "additional_daily_hours": None,
                       "message": f"No study day falls between {today.isoformat()} and {deadline.isoformat()}: choose more weekdays or a later deadline."}
    else:
        required = remaining / usable
        feasibility = {"status": "infeasible", "required_daily_hours": round(required, 2), "additional_daily_hours": round(max(0.0, required - daily_hours), 2),
                       "message": f"At {daily_hours:g} h on your study days you finish on {finish.isoformat() if finish else 'no date within ten years'}, after {deadline.isoformat()}. "
                                  f"To finish by then you need {required:.2f} h on each of the {usable} study days (about {max(0.0, required - daily_hours):.2f} h more a day)."
                                  + (" That is more than 24 hours a day." if required > 24 else "")}
    result["feasibility"] = {"deadline": deadline.isoformat(), **feasibility}
    return result


def _escape(text):
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _fold(line):
    """RFC 5545 line folding: no line longer than 75 octets, continuation lines start with one space (never splitting a UTF-8 character)."""
    data, out = line.encode("utf-8"), []
    while len(data) > 75:
        cut = 75 if not out else 74
        while data[cut] & 0xC0 == 0x80:
            cut -= 1
        out.append(data[:cut].decode("utf-8"))
        data = data[cut:]
    out.append(data.decode("utf-8"))
    return "\r\n ".join(out)


def add_reviews(calendar, review_schedule, minutes_per_review=1.5):
    """Put spaced reviews into a built calendar: `calendar["reviews"]` is [{date, count, minutes, concepts}] for each review day of the schedule (see spaced_review.schedule) within the
    calendar's span or beyond it, and `deferred_reviews` the count the cap and horizon left out. Study items are not changed."""
    days = []
    for day in review_schedule["days"]:
        days.append({"date": day["date"], "count": day["count"], "minutes": round(day["count"] * minutes_per_review, 1), "concepts": sorted({i["concept"] for i in day["items"] if i.get("concept")})})
    calendar["reviews"], calendar["deferred_reviews"], calendar["review_cap"] = days, len(review_schedule["deferred"]), review_schedule["cap"]
    return calendar


def to_ics(calendar, title="PreReqAI study plan", timezone_name="UTC", start_at=time(9, 0), now=None):
    """The calendar as an iCalendar document (CRLF lines). Each scheduled item is one event, back to back from `start_at` local time in `timezone_name`
    (an IANA name such as Europe/Berlin); times are written in UTC, so no VTIMEZONE is needed and every client agrees, and a day with a clock change
    keeps its local start time. CalendarError for an unknown time zone."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise CalendarError(f"{timezone_name!r} is not a time zone name (use one like UTC or Europe/Berlin)") from None
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PreReqAI//Study plan//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{_escape(title)}"]
    for day in calendar["days"]:
        begin = datetime.combine(date.fromisoformat(day["date"]), start_at, tzinfo=zone)
        for item in day["items"]:
            end = begin + timedelta(minutes=round(item["hours"] * 60))
            uid = hashlib.sha1(f"{title}|{day['date']}|{item['concept']}".encode("utf-8")).hexdigest()[:24] + "@prereqai"
            hours, concept = format(item["hours"], "g"), item["concept"]
            lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART:{begin.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                      f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "SUMMARY:" + _escape("Study " + concept),
                      "DESCRIPTION:" + _escape(hours + " h of " + concept + " (" + title + ")"), "END:VEVENT"]
            begin = end
    for day in calendar.get("reviews", []):  # spaced reviews: one event a day, after that day's study items
        begin = datetime.combine(date.fromisoformat(day["date"]), start_at, tzinfo=zone) + timedelta(minutes=round(sum(i["hours"] for d in calendar["days"] if d["date"] == day["date"] for i in d["items"]) * 60))
        end = begin + timedelta(minutes=max(1, round(day["minutes"])))
        uid = hashlib.sha1(f"{title}|{day['date']}|reviews".encode("utf-8")).hexdigest()[:24] + "@prereqai"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART:{begin.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                  f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "SUMMARY:" + _escape(f"Review {day['count']} question{'s' if day['count'] != 1 else ''}"),
                  "DESCRIPTION:" + _escape("Spaced review of " + (", ".join(day["concepts"]) or "your questions") + " (" + title + ")"), "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
