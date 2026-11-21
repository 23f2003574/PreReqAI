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


GRADED_FIELDS = ("graded_attempts", "graded_correct", "graded_streak", "high_confidence_right", "high_confidence_wrong")


def _graded(entry, graded):
    """The assessment counters of an entry after one more answer. `graded` is None for a self-reported answer (the counters are then only carried over, and are absent from an entry that
    never had an assessed answer) or {"correct": bool, "confidence": "low"|"medium"|"high"} for an answer the system checked itself."""
    carried = {name: entry[name] for name in GRADED_FIELDS if name in entry}
    if graded is None:
        return carried
    counters = {name: carried.get(name, 0) for name in GRADED_FIELDS}
    counters["graded_attempts"] += 1
    counters["graded_correct"] += bool(graded["correct"])
    counters["graded_streak"] = counters["graded_streak"] + 1 if graded["correct"] else 0
    if graded.get("confidence") == "high":
        counters["high_confidence_right" if graded["correct"] else "high_confidence_wrong"] += 1
    return counters


def update(entry, concept, outcome, moment, graded=None):
    """The entry of a question after one more answer (`knew` or `missed`) at `moment`; `entry` (or None for a first answer) is not changed."""
    entry = dict(entry or {})
    knew, missed = entry.get("knew", 0) + (outcome == "knew"), entry.get("missed", 0) + (outcome != "knew")
    streak = entry.get("streak", 0) + 1 if outcome == "knew" else 0
    wait = interval(streak, knew, missed)
    extra = _graded(entry, graded)
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
