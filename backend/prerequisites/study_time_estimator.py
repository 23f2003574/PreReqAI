import math

from backend.models import (
    Paper,
    StudyTimeEstimate,
)


DEFAULT_HOURS_PER_DAY = 3.0  # the fixed assumption before the learner could choose
MAX_HOURS_PER_DAY = 24.0


def parse_hours_per_day(value) -> float:
    """The learner's daily study hours as a float: None is the default; a number or numeric text above 0 and at most 24 is accepted.
    Anything else (zero, negative, text, NaN, infinity, a boolean, more than a day) raises ValueError saying what is wrong."""
    if value is None:
        return DEFAULT_HOURS_PER_DAY
    if isinstance(value, bool):
        raise ValueError("hours per day must be a number of hours, not true/false")
    try:
        hours = float(value.strip() if isinstance(value, str) else value)
    except (TypeError, ValueError):
        raise ValueError(f"hours per day must be a number of hours, not {value!r}") from None
    if not math.isfinite(hours):
        raise ValueError(f"hours per day must be a finite number, not {value!r}")
    if hours <= 0:
        raise ValueError(f"hours per day must be greater than 0, not {value!r}")
    if hours > MAX_HOURS_PER_DAY:
        raise ValueError(f"hours per day cannot be more than {MAX_HOURS_PER_DAY:g}, not {value!r}")
    return hours


def _needs(concept, rules):
    """Every subject `concept` depends on, directly or through other subjects, by the prerequisite rule table."""
    found, pending = set(), list(rules.get(concept, ()))
    while pending:
        item = pending.pop()
        if item not in found:
            found.add(item)
            pending.extend(rules.get(item, ()))
    return found


def schedule_order(steps, importance) -> list:
    """The plan's steps in the order they are scheduled: essential prerequisites before supporting ones, but never before a subject
    they depend on (by the prerequisite rule table), so the plan's foundations-first order is kept where it matters. Ties keep plan order.
    Without importance data the plan order is used unchanged."""
    if not any(importance.get(step.concept) for step in steps):
        return list(steps)
    from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

    rules, planned = PrerequisiteDetector.PREREQUISITE_RULES, {step.concept for step in steps}
    needs = {step.concept: _needs(step.concept, rules) & planned for step in steps}
    remaining, done, ordered = list(steps), set(), []
    while remaining:
        ready = [step for step in remaining if needs[step.concept] <= done] or remaining[:1]
        pick = next((step for step in ready if importance.get(step.concept) == "essential"), ready[0])
        remaining.remove(pick)
        done.add(pick.concept)
        ordered.append(pick)
    return ordered


def build_schedule(steps, hours_per_day, importance=None) -> list:
    """[{day, hours, items: [{concept, hours}]}]: the steps' own estimated hours filled into days of `hours_per_day`; a step that
    does not fit the rest of a day continues on the next one."""
    days, items, room = [], [], hours_per_day
    for step in schedule_order(steps, importance or {}):
        left = step.estimated_hours
        while left > 1e-9:
            take = min(left, room)
            items.append({"concept": step.concept, "hours": round(take, 2)})
            left, room = left - take, room - take
            if room <= 1e-9:
                days.append({"day": len(days) + 1, "hours": round(sum(item["hours"] for item in items), 2), "items": items})
                items, room = [], hours_per_day
    if items:
        days.append({"day": len(days) + 1, "hours": round(sum(item["hours"] for item in items), 2), "items": items})
    return days


class StudyTimeEstimator:
    """
    Estimates the study time required before
    reading a research paper, and spreads it over
    days of the learner's available hours (3 by default).
    """

    def estimate(
        self,
        paper: Paper,
    ) -> Paper:

        try:
            hours_per_day = parse_hours_per_day(getattr(paper, "hours_per_day", None))
        except ValueError:  # a damaged saved session must not stop the estimate
            hours_per_day = DEFAULT_HOURS_PER_DAY

        total_hours = sum(

            step.estimated_hours

            for step in paper.learning_plan
        )

        importance = {item.concept: item.importance for item in getattr(paper, "prerequisites", [])}

        schedule = build_schedule(paper.learning_plan, hours_per_day, importance)

        recommended_days = max(1, len(schedule))

        paper.study_time = StudyTimeEstimate(

            total_hours=total_hours,

            recommended_days=recommended_days,

            average_hours_per_day=round(

                total_hours /

                recommended_days,

                1,
            ),

            daily_hours=hours_per_day,

            schedule=schedule,
        )

        return paper
