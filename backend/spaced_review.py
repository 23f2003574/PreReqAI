"""The spaced-review policy: when a quiz question is due again, from how the learner answered and how long ago.

A question the learner knew moves up a ladder of intervals (1, 3, 7, 14, 30 and 60 days), one rung per correct answer in a row, so a question
answered correctly is never due again at once. A missed question drops to the bottom: it is due again in 4 hours, and its streak starts over. A
question the learner has missed at least as often as they knew is weak: a correct answer to it climbs only to half the rung it earned
(never below 1 day), so it comes back sooner than a strong one. Times are UTC and stored as ISO 8601 strings ("2026-11-20T10:00:00Z")."""
from datetime import datetime, timedelta, timezone

LADDER_DAYS = (1, 3, 7, 14, 30, 60)
MISSED_RETRY = timedelta(hours=4)
_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime(_FORMAT)


def parse_time(text):
    """The moment of a stored stamp (UTC), or None when it is not one."""
    try:
        return datetime.strptime(text, _FORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def interval(streak, knew, missed):
    """The wait after an answer that left `streak` correct answers in a row (0 after a miss), with `knew` and `missed` the totals so far."""
    if streak <= 0:
        return MISSED_RETRY
    days = LADDER_DAYS[min(streak, len(LADDER_DAYS)) - 1]
    if missed >= knew:  # a weak question comes back sooner
        days = max(1, days / 2)
    return timedelta(days=days)


MAX_CONFUSIONS = 8  # the other concepts one question's wrong answers are most often taken for
GRADED_FIELDS = ("graded_attempts", "graded_correct", "graded_streak", "high_confidence_right", "high_confidence_wrong")


HISTORY_LIMIT = 20  # growth policy: an entry keeps its last 20 graded answers in order, each with the time it was given (profile schema 3; schema 2 kept 8 without times); older ones survive as counters, so a profile's size is bounded by questions x 20 short codes
_CONFIDENCE_CODE = {"low": "l", "medium": "m", "high": "h"}


def _confusions(entry, graded):
    """{concept: times} the learner has picked another concept's answer for this question: the entry's earlier counts plus this answer's `confused_with` when it was wrong. Empty when there is none."""
    found = {k: v for k, v in (entry.get("confusions") or {}).items() if isinstance(k, str) and isinstance(v, int) and v > 0}
    if graded and not graded.get("correct") and graded.get("confused_with"):
        found[graded["confused_with"]] = found.get(graded["confused_with"], 0) + 1
    return dict(sorted(found.items(), key=lambda item: (-item[1], item[0]))[:MAX_CONFUSIONS])


def _graded(entry, graded, moment=None):
    result = _graded_counters(entry, graded, moment)
    confusions = _confusions(entry, graded)
    return {**result, **({"confusions": confusions} if confusions else {})}


def _graded_counters(entry, graded, moment=None):
    """The assessment counters of an entry after one more answer. `graded` is None for a self-reported answer (the counters are then only carried over, and are absent from an entry that
    never had an assessed answer) or {"correct": bool, "confidence": "low"|"medium"|"high"} for an answer the system checked itself. `graded_history` holds the last HISTORY_LIMIT assessed answers
    in order as codes (`graded_first_at` keeps the time of the first timed answer, see backend/mastery_model.py): correct 1 or 0, then confidence l, m or h, then "@" and the UTC time the answer was given when it is known ("1h@2026-11-23T13:03:48Z" is a correct answer given with high confidence at that time; a bare "1h" comes from a schema 2 profile and has no known time)."""
    carried = {name: entry[name] for name in GRADED_FIELDS if name in entry}
    history = [code for code in entry.get("graded_history", []) if isinstance(code, str)]
    first_at = entry.get("graded_first_at") if parse_time(entry.get("graded_first_at")) is not None else None
    if graded is None:
        return {**carried, **({"graded_history": history[-HISTORY_LIMIT:]} if history else {}), **({"graded_first_at": first_at} if first_at else {})}
    counters = {name: carried.get(name, 0) for name in GRADED_FIELDS}
    counters["graded_attempts"] += 1
    counters["graded_correct"] += bool(graded["correct"])
    counters["graded_streak"] = counters["graded_streak"] + 1 if graded["correct"] else 0
    if graded.get("confidence") == "high":
        counters["high_confidence_right" if graded["correct"] else "high_confidence_wrong"] += 1
    history.append(("1" if graded["correct"] else "0") + _CONFIDENCE_CODE.get(graded.get("confidence"), "m") + (f"@{stamp(moment)}" if moment is not None else ""))
    if first_at is None:  # the time of the first timed answer survives when that answer rolls out of the kept history, so what the history forgot is not mistaken for a separate sitting
        first_at = next((code[3:] for code in history if len(code) > 3 and code[2] == "@"), None)
    return {**counters, "graded_history": history[-HISTORY_LIMIT:], **({"graded_first_at": first_at} if first_at else {})}


GRADES = ("again", "hard", "good", "easy")
EASE_START = {"Easy": 2.7, "Medium": 2.5, "Hard": 2.3}  # the question's own difficulty sets how fast its interval may grow
MIN_EASE, MAX_EASE, MAX_INTERVAL_DAYS = 1.3, 3.5, 365
_GRADE_FACTOR = {"hard": 0.6, "good": 1.0, "easy": 1.4}
_EASE_CHANGE = {"again": -0.2, "hard": -0.15, "good": 0.0, "easy": 0.15}


def graded_update(entry, concept, grade, moment, difficulty="Medium", graded=None):
    """The entry of a question after a review answered with one of GRADES (again, hard, good, easy). Each question has its own `ease` (starting from its difficulty, then raised or lowered
    by every grade, between MIN_EASE and MAX_EASE). `again` resets the streak and returns in MISSED_RETRY; the first two successes wait 1 and 3 days, later ones the previous wait times the
    ease; `hard` waits 0.6 of that, `easy` 1.4 of it, never less than 12 hours or more than MAX_INTERVAL_DAYS. `last_outcome` stays knew/missed (again is missed) so older readers keep working."""
    if grade not in GRADES:
        raise ValueError(f"a grade is one of {', '.join(GRADES)}, not {grade!r}")
    entry = dict(entry or {})
    outcome = "missed" if grade == "again" else "knew"
    knew, missed = entry.get("knew", 0) + (outcome == "knew"), entry.get("missed", 0) + (outcome == "missed")
    streak = entry.get("streak", 0) + 1 if outcome == "knew" else 0
    ease = round(min(MAX_EASE, max(MIN_EASE, entry.get("ease", EASE_START.get(difficulty, 2.5)) + _EASE_CHANGE[grade])), 2)
    if grade == "again":
        wait = MISSED_RETRY
    else:
        base_hours = 24.0 if streak == 1 else 72.0 if streak == 2 else max(24.0, entry.get("interval_hours", 24.0)) * ease
        wait = timedelta(hours=min(MAX_INTERVAL_DAYS * 24, max(12.0, base_hours * _GRADE_FACTOR[grade])))
    return {**_graded(entry, graded, moment), "concept": concept, "attempts": knew + missed, "knew": knew, "missed": missed, "streak": streak, "last_outcome": outcome, "last_grade": grade, "ease": ease,
            "first_seen": entry.get("first_seen") or stamp(moment), "last_seen": stamp(moment), "interval_hours": round(wait.total_seconds() / 3600, 2), "due": stamp(moment + wait)}


def schedule(items, today, cap=10, horizon_days=30):
    """Lay review items out over days without ever exceeding `cap` per day. `items` are queue entries ({question_id, concept, due}); `today` a date. Overdue and due-today items are placed
    from today, most overdue first, `cap` a day, so a long absence becomes a few capped days, never one huge day; an item due on a later day is placed on that day or the first one with
    room. Items that would fall after `horizon_days` days from today are returned as `deferred` (still due, not scheduled). Returns {"days": [{date, count, items}], "deferred": [...],
    "cap", "backlog_days"}: backlog_days is how many days the overdue backlog takes to clear."""
    from datetime import date as _date

    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
        raise ValueError("the daily review cap must be a whole number of at least 1")
    ordered = sorted(items, key=lambda item: (parse_time(item["due"]) or datetime.max.replace(tzinfo=timezone.utc), item["question_id"]))
    load, placed, deferred, overdue_days = {}, {}, [], set()
    for item in ordered:
        due = parse_time(item["due"])
        day = max(today, due.date()) if due else today
        while load.get(day, 0) >= cap:
            day += timedelta(days=1)
        if (day - today).days > horizon_days:
            deferred.append(item)
            continue
        load[day] = load.get(day, 0) + 1
        placed.setdefault(day, []).append(item)
        if due and due.date() <= today:
            overdue_days.add(day)
    days = [{"date": day.isoformat(), "count": len(entries), "items": [{"question_id": e["question_id"], "concept": e.get("concept")} for e in entries]} for day, entries in sorted(placed.items())]
    return {"days": days, "deferred": [{"question_id": e["question_id"], "concept": e.get("concept"), "due": e["due"]} for e in deferred], "cap": cap, "backlog_days": len(overdue_days)}


def update(entry, concept, outcome, moment, graded=None):
    """The entry of a question after one more answer (`knew` or `missed`) at `moment`; `entry` (or None for a first answer) is not changed."""
    entry = dict(entry or {})
    knew, missed = entry.get("knew", 0) + (outcome == "knew"), entry.get("missed", 0) + (outcome != "knew")
    streak = entry.get("streak", 0) + 1 if outcome == "knew" else 0
    wait = interval(streak, knew, missed)
    extra = _graded(entry, graded, moment)
    return {**extra, "concept": concept, "attempts": knew + missed, "knew": knew, "missed": missed, "streak": streak, "last_outcome": outcome,
            "first_seen": entry.get("first_seen") or stamp(moment), "last_seen": stamp(moment), "interval_hours": round(wait.total_seconds() / 3600, 2),
            "due": stamp(moment + wait)}


def queue(questions, moment, upcoming_limit=10):
    """{"due": [...], "upcoming": [...], "concepts": [...]} from {question_id: entry}. Due items (due time reached) come most overdue first; each has
    `overdue_hours`. Upcoming items are the next ones by due time. `concepts` gives each concept's earliest due question and its mastery state."""
    items = []
    for identifier, entry in questions.items():
        due = parse_time(entry.get("due"))
        if due is None:
            continue
        items.append({"question_id": identifier, "concept": entry.get("concept"), "due": entry["due"], "last_outcome": entry.get("last_outcome"),
                      "streak": entry.get("streak", 0), "overdue_hours": round(max(0.0, (moment - due).total_seconds() / 3600), 2), "_at": due})
    items.sort(key=lambda item: (item["_at"], item["question_id"]))
    due_now = [item for item in items if item["_at"] <= moment]
    later = [item for item in items if item["_at"] > moment][:upcoming_limit]
    by_concept = {}
    for item in items:
        by_concept.setdefault(item["concept"], item)
    concepts = [{"concept": name, "next_due": first["due"], "is_due": first["_at"] <= moment} for name, first in sorted(by_concept.items(), key=lambda pair: pair[1]["_at"])]
    for item in items:
        del item["_at"]
    return {"due": due_now, "upcoming": later, "concepts": concepts}
