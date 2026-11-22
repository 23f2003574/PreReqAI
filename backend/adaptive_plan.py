"""A study plan that adapts to what the learner has shown (assessed answers), with every change explained and reversible.

Input: the analysis report's plan (study_calendar.plan_inputs), the session's assessed attempts (graded diagnostic answers, see tutor/diagnostic.py) and the learner's overrides. Rules:
* compress: at least MIN_GRADED assessed answers on at least MIN_DISTINCT different questions of the step's subject, accuracy at least COMPRESS_ACCURACY, no confidently wrong answer:
  the step's hours become COMPRESS_FACTOR of the original (never below MIN_HOURS or above the original); it stays in the plan;
* remediate: at least 2 assessed answers with accuracy at most REMEDIATE_ACCURACY, or two confidently wrong answers: hours grow by REMEDIATE_FACTOR (at most +50 percent) and the
  questions missed come back as a remediation list (question, correct answer, explanation);
* otherwise the step is kept as planned (too little evidence is never a reason to change a plan).
Self-reported answers are not evidence here. A learner's override ("reject") restores a step to its original hours; "restore" brings the adaptation back. Nothing is saved by this module."""
from math import isfinite

MIN_GRADED, MIN_DISTINCT = 3, 2
COMPRESS_LOWER = 0.80  # the lower end of the mastery estimate (backend/mastery_model.py) must reach this before a step is compressed
COMPRESS_ACCURACY, COMPRESS_FACTOR, MIN_HOURS = 0.85, 0.3, 0.5
REMEDIATE_ACCURACY, REMEDIATE_FACTOR = 0.5, 1.5


def evidence_from_attempts(attempts):
    """{concept: {graded, correct, distinct_correct, high_confidence_wrong, missed: [question ids]}} from the assessed attempts only."""
    found, per_concept = {}, {}
    for attempt in attempts:
        if not attempt.get("graded"):
            continue
        per_concept.setdefault(attempt["concept"], []).append(attempt)
        entry = found.setdefault(attempt["concept"], {"graded": 0, "correct": 0, "correct_questions": set(), "high_confidence_wrong": 0, "missed": []})
        entry["graded"] += 1
        if attempt["correct"]:
            entry["correct"] += 1
            entry["correct_questions"].add(attempt["question_id"])
        else:
            entry["missed"].append(attempt["question_id"])
            entry["high_confidence_wrong"] += attempt.get("confidence") == "high"
    for entry in found.values():
        entry["distinct_correct"] = len(entry.pop("correct_questions"))
        entry["missed"] = list(dict.fromkeys(entry["missed"]))
    from backend import mastery_model

    for concept, entry in found.items():  # the same estimate the profile uses, over this session's answers in the order they were given
        estimate = mastery_model.estimate_attempts(per_concept[concept])
        entry.update({"p_mastery": estimate["p"], "mastery_low": estimate["low"], "mastery_high": estimate["high"], "mastered": estimate["mastered"]})
    return found


def _remediation(question_ids):
    from backend.tutor.quiz_bank import QUIZ_EXPLANATIONS
    from backend.tutor.quiz_session import QuizError, _lookup

    items = []
    for identifier in question_ids:
        try:
            concept, _, item = _lookup(identifier)
        except QuizError:
            continue
        items.append({"question_id": identifier, "question": item["question"], "answer": item["answer"], "explanation": QUIZ_EXPLANATIONS.get((concept, item["question"]), "")})
    return items


def decide(concept, hours, evidence):
    """(action, factor, reason) for one step from its assessed evidence."""
    if not evidence:
        return "keep", 1.0, "No assessed answers yet: the plan is unchanged. Answer a few diagnostic questions to adapt it."
    graded, correct, accuracy = evidence["graded"], evidence["correct"], evidence["correct"] / evidence["graded"]
    summary = f"{correct} of {graded} assessed answers correct"
    if evidence["high_confidence_wrong"] >= 2 or (graded >= 2 and accuracy <= REMEDIATE_ACCURACY):
        why = f"{summary}" + (f", {evidence['high_confidence_wrong']} of the misses with high confidence" if evidence["high_confidence_wrong"] else "")
        return "remediate", REMEDIATE_FACTOR, f"{why}: more time is planned and the questions you missed are listed to review."
    if str(concept).startswith("Math: ") and evidence.get("mastered"):  # a mathematical skill the learner has demonstrated (see math_plan.py): the step can be skipped
        return "skip", 0.0, f"{summary}, estimated {evidence['p_mastery']:.2f} probability of knowing it: mastery is demonstrated, so this step can be skipped (reject to study it anyway)."
    if graded >= MIN_GRADED and evidence["distinct_correct"] >= MIN_DISTINCT and accuracy >= COMPRESS_ACCURACY and not evidence["high_confidence_wrong"] \
            and evidence.get("mastery_low", 1.0) >= COMPRESS_LOWER:
        return "compress", COMPRESS_FACTOR, f"{summary} across {evidence['distinct_correct']} different questions: a short refresher is planned instead of the full study time."
    return "keep", 1.0, f"{summary}{' (estimated probability of knowing it ' + format(evidence['p_mastery'], '.2f') + ', at least ' + format(evidence['mastery_low'], '.2f') + ')' if 'p_mastery' in evidence else ''}: not yet enough to change the plan (compressing needs {MIN_GRADED} answers on {MIN_DISTINCT} questions at {int(COMPRESS_ACCURACY * 100)}%)."


def propose(report, attempts, overrides=None, calendar=None):
    """{"adjustments": [...], "plan": [...], "remediation": {concept: [...]}, "hours_before", "hours_after", "feasibility"} for the report's unstudied steps. `calendar` is None or a dict
    {today: date, deadline, daily_hours, weekdays}; with it the schedule before and after is checked against the deadline."""
    from backend import study_calendar

    steps, importance, _ = study_calendar.plan_inputs(report)
    evidence, overrides = evidence_from_attempts(attempts), overrides or {}
    adjustments, plan, remediation = [], [], {}
    for step in steps:
        action, factor, reason = decide(step.concept, step.estimated_hours, evidence.get(step.concept))
        original = step.estimated_hours
        adjusted = original
        if action == "compress":
            adjusted = round(min(original, max(MIN_HOURS, original * factor)), 2)
        elif action == "remediate":
            adjusted = round(original * factor, 2)
        elif action == "skip":
            adjusted = 0.0
        overridden = overrides.get(step.concept) == "reject" and action != "keep"
        if overridden:
            adjusted = original
        if action == "remediate" and not overridden:
            remediation[step.concept] = _remediation(evidence[step.concept]["missed"])
        if action != "keep" or step.concept in evidence:
            adjustments.append({"concept": step.concept, "action": action, "original_hours": original, "adjusted_hours": adjusted, "reason": reason, "overridden": overridden,
                                "evidence": {k: v for k, v in evidence.get(step.concept, {}).items()}, "can_override": action != "keep"})
        plan.append({"concept": step.concept, "hours": adjusted, "original_hours": original, "adapted": adjusted != original, "importance": importance.get(step.concept)})
    result = {"adjustments": adjustments, "plan": plan, "remediation": remediation, "hours_before": round(sum(s.estimated_hours for s in steps), 2), "hours_after": round(sum(p["hours"] for p in plan), 2)}
    if calendar:
        from types import SimpleNamespace

        def schedule(hours_of):
            built = study_calendar.build_calendar([SimpleNamespace(concept=s.concept, estimated_hours=hours_of(s)) for s in steps], importance, calendar["daily_hours"], calendar["today"],
                                                  calendar.get("weekdays"), calendar.get("deadline"))
            return {"finish_date": built["finish_date"], **built["feasibility"]}

        paid = {p["concept"]: p["hours"] for p in plan}
        result["feasibility"] = {"before": schedule(lambda s: s.estimated_hours), "after": schedule(lambda s: paid[s.concept])}
    return result


def clean_hours(value):
    return isinstance(value, (int, float)) and isfinite(value)


def adapted_report(report, attempts, overrides=None):
    """The report with its learning_plan hours replaced by the adapted ones (steps carry `adapted: True` and `original_hours`; `adapted_concepts` lists them), so the calendar, plan
    text and curriculum all schedule what the learner's assessed answers call for. Without any adaptation the very same report object is returned, so nothing downstream changes."""
    changed = {item["concept"]: item["hours"] for item in propose(report, attempts, overrides)["plan"] if item["adapted"]}
    if not changed:
        return report
    def adapt(step):
        if step["concept"] not in changed:
            return step
        hours = changed[step["concept"]]
        return {**step, "estimated_hours": hours, "original_hours": step["estimated_hours"], "adapted": True, **({"skipped": True} if hours <= 0 else {})}

    found = {**report, "learning_plan": [adapt(step) for step in report.get("learning_plan", [])], "adapted_concepts": sorted(changed)}
    if report.get("math_plan"):
        found["math_plan"] = [adapt(step) for step in report["math_plan"]]
    return found


def session_report(session, adapted=True):
    """The session's report as the schedule should see it: adapted to its assessed answers and the learner's overrides unless `adapted` is False."""
    report = session.report
    return adapted_report(report, getattr(session, "quiz_attempts", []) or [], report.get("adaptive_overrides", {})) if adapted else report
