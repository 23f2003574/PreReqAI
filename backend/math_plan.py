"""Mathematical gaps as study steps: each skill the paper's equations need (report["math_subtopics"]) becomes a step "Math: <subtopic>" with hours, a study link and a diagnostic.

The hours of a step are SHARE of the curated course hours of its broad subject (never below MIN_HOURS): a focused part of the course, not the whole subject. This is a planning heuristic, not a
measurement. A step has diagnostic questions when `backend/tutor/math_quiz.py` has them for the subtopic (`diagnostic: True`). The steps go after the paper's own plan steps and are scheduled and
adapted with them (study_calendar.plan_inputs, adaptive_plan): objectively graded answers that show mastery (backend/mastery_model.py) make a step skippable, with the learner able to reject that."""
SHARE, MIN_HOURS = 0.15, 1.0
PREFIX = "Math: "


def build(subtopics):
    """[{step, concept, subtopic, subject, estimated_hours, why, equation_count, resource, diagnostic}] for the report's ranked math subtopics."""
    from backend.tutor.math_quiz import MATH_QUIZ

    steps = []
    for number, item in enumerate(subtopics, start=1):
        resource = item.get("resource") or {}
        hours = max(MIN_HOURS, round(float(resource.get("hours") or 0) * SHARE, 1))
        name = PREFIX + item["subtopic"]
        steps.append({"step": number, "concept": name, "subtopic": item["subtopic"], "subject": item["subject"], "estimated_hours": hours, "why": item["why"],
                      "equation_count": item["equation_count"], "resource": item.get("resource"), "diagnostic": name in MATH_QUIZ})
    return steps


def is_math(concept):
    return str(concept).startswith(PREFIX)
