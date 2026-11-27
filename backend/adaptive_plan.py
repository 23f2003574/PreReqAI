"""A study plan that adapts to what the learner has shown (assessed answers), with every change explained and reversible.

Input: the analysis report's plan (study_calendar.plan_inputs), the session's assessed attempts (graded diagnostic answers, see tutor/diagnostic.py) and the learner's overrides. Rules:
* compress: at least MIN_GRADED assessed answers on at least MIN_DISTINCT different questions of the step's subject, accuracy at least COMPRESS_ACCURACY, no confidently wrong answer:
  the step's hours become COMPRESS_FACTOR of the original (never below MIN_HOURS or above the original); it stays in the plan;
* remediate: at least 2 assessed answers with accuracy at most REMEDIATE_ACCURACY, or two confidently wrong answers: hours grow by REMEDIATE_FACTOR (at most +50 percent) and the
  questions missed come back as a remediation list (question, correct answer, explanation);
* otherwise the step is kept as planned (too little evidence is never a reason to change a plan).
Evidence also comes from the learner's persistent profile (earlier sessions and papers): a concept the profile rates "mastered" by the assessed-answer estimate (backend/learner_profile.mastery) counts as evidence for a step on that concept when this session has none of its own, so a prerequisite already demonstrated is shortened (or, for a mathematical skill, skipped) in a new paper's plan, with the reason saying the evidence is from the profile. A profile concept that is "needs_refresh" (its reviews are long overdue), "progressing", "needs_practice" or self-reported never changes a plan, and this session's own assessed answers always win over the profile's. Self-reported answers are not evidence here. A concept the profile rates "needs_refresh" (mastered once, then lapsed under the forgetting model of backend/mastery_model.py) gets a "refresh" step: REFRESH_FACTOR of the original hours (never below MIN_HOURS or above the original), with the reason naming the probability at the last answer, the days since and the decayed probability, so lapsed knowledge is revisited briefly instead of studied from scratch or ignored; this session's own assessed answers win over it, and a "reject" override restores the full hours. A learner's override ("reject") restores a step to its original hours; "restore" brings the adaptation back. Nothing is saved by this module."""
from math import isfinite

MIN_GRADED, MIN_DISTINCT = 3, 2
COMPRESS_LOWER = 0.80  # the lower end of the mastery estimate (backend/mastery_model.py) must reach this before a step is compressed
COMPRESS_ACCURACY, COMPRESS_FACTOR, MIN_HOURS = 0.85, 0.3, 0.5
REMEDIATE_ACCURACY, REMEDIATE_FACTOR = 0.5, 1.5
REMEDIATE_P = 0.5  # low lifetime accuracy asks for more time only while the mastery estimate (which weighs the order of the answers) is also below this: a learner who has since recovered is not given the extra hours
REFRESH_FACTOR = 0.5  # a lapsed concept was once demonstrated, so a refresh takes half the original study time (a stated heuristic)


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
        entry.update({"p_mastery": estimate["p"], "mastery_low": estimate["low"], "mastery_high": estimate["high"], "mastered": estimate["mastered"], "spaced": estimate["timed"] and estimate["spaced_blocks"] >= mastery_model.MIN_BLOCKS})
    return found


def profile_evidence(quiz, now=None):
    """{concept: evidence} in the shape of evidence_from_attempts for the concepts a learner profile's quiz history rates "mastered" (assessed answers only, still fresh: see learner_profile.mastery), each marked
    "source": "profile". Concepts in any other state, and a profile that cannot be used, give nothing."""
    from backend import learner_profile, mastery_model

    found = {}
    for item in learner_profile.mastery(quiz or {}, now):
        if item["status"] != "mastered" or item.get("evidence") != "assessed":
            continue
        found[item["concept"]] = {"graded": item["graded_attempts"], "correct": item["graded_correct"], "distinct_correct": min(item["questions"], item["graded_correct"]), "high_confidence_wrong": item["high_confidence_wrong"],
                                  "missed": [], "p_mastery": item["p_mastery"], "mastery_low": item["mastery_low"], "mastery_high": item["mastery_high"], "mastered": True, "spaced": item.get("spaced_blocks", 0) >= mastery_model.MIN_BLOCKS, "source": "profile"}
    return found


def lapsed_evidence(quiz, now=None):
    """{concept: {"lapsed": True, ...}} for the concepts a learner profile's quiz history rates "needs_refresh": assessed mastery that the forgetting model has let lapse (see learner_profile.mastery). Marked "source": "profile"."""
    from backend import learner_profile

    return {item["concept"]: {"lapsed": True, "source": "profile", "p_mastery": item["p_mastery"], "p_at_last_answer": item.get("p_at_last_answer"), "days_since_evidence": item.get("days_since_evidence"),
                              "graded": item["graded_attempts"], "correct": item["graded_correct"], "high_confidence_wrong": item["high_confidence_wrong"], "missed": []}
            for item in learner_profile.mastery(quiz or {}, now) if item["status"] == "needs_refresh" and item.get("evidence") == "assessed"}


def profile_quiz(session):
    """The quiz history of the session's learner profile, or None when the session has no profile, the profiles directory is not configured or the file cannot be read."""
    from backend import learner_profile

    directory = learner_profile.configured_directory()
    name = getattr(session, "profile", None)
    if not directory or not name:
        return None
    try:
        profile, problem = learner_profile.load_cached(learner_profile.profile_path(directory, name))
    except (learner_profile.ProfileError, OSError):
        return None
    return None if problem else profile["quiz"]


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
    if evidence and evidence.get("lapsed"):
        days, earlier = evidence.get("days_since_evidence"), evidence.get("p_at_last_answer")
        was = (f"estimated {earlier:.2f} at the last graded answer" if earlier is not None else "mastery shown") + (f", {days:.0f} days ago" if isinstance(days, (int, float)) else "")
        return "refresh", REFRESH_FACTOR, (f"you showed mastery in your learner profile ({was}), and the forgetting model now puts it at {evidence['p_mastery']:.2f}: "
                                           "a short refresh is planned instead of the full study time; answering a few questions again will confirm it.")
    if not evidence:
        return "keep", 1.0, "No assessed answers yet: the plan is unchanged. Answer a few diagnostic questions to adapt it."
    graded, correct, accuracy = evidence["graded"], evidence["correct"], evidence["correct"] / evidence["graded"]
    summary = f"{correct} of {graded} assessed answers correct" + (" in your learner profile (earlier sessions)" if evidence.get("source") == "profile" else "")
    if evidence["high_confidence_wrong"] >= 2 or (graded >= 2 and accuracy <= REMEDIATE_ACCURACY and evidence.get("p_mastery", 0.0) < REMEDIATE_P):
        why = f"{summary}" + (f", {evidence['high_confidence_wrong']} of the misses with high confidence" if evidence["high_confidence_wrong"] else "")
        return "remediate", REMEDIATE_FACTOR, f"{why}: more time is planned and the questions you missed are listed to review."
    if str(concept).startswith("Math: ") and evidence.get("mastered") and evidence.get("spaced"):  # a mathematical skill the learner has demonstrated (see math_plan.py): the step can be skipped
        return "skip", 0.0, f"{summary}, estimated {evidence['p_mastery']:.2f} probability of knowing it: mastery is demonstrated, so this step can be skipped (reject to study it anyway)."
    if graded >= MIN_GRADED and evidence["distinct_correct"] >= MIN_DISTINCT and accuracy >= COMPRESS_ACCURACY and not evidence["high_confidence_wrong"] \
            and evidence.get("mastery_low", 1.0) >= COMPRESS_LOWER:
        return "compress", COMPRESS_FACTOR, f"{summary} across {evidence['distinct_correct']} different questions: a short refresher is planned instead of the full study time."
    return "keep", 1.0, f"{summary}{' (estimated probability of knowing it ' + format(evidence['p_mastery'], '.2f') + ', at least ' + format(evidence['mastery_low'], '.2f') + ')' if 'p_mastery' in evidence else ''}: not yet enough to change the plan (compressing needs {MIN_GRADED} answers on {MIN_DISTINCT} questions at {int(COMPRESS_ACCURACY * 100)}%)."


def propose(report, attempts, overrides=None, calendar=None, profile=None, now=None):
    """{"adjustments": [...], "plan": [...], "remediation": {concept: [...]}, "hours_before", "hours_after", "feasibility"} for the report's unstudied steps. `profile` is None or the quiz history of the learner's profile (see profile_evidence); `calendar` is None or a dict
    {today: date, deadline, daily_hours, weekdays}; with it the schedule before and after is checked against the deadline."""
    from backend import study_calendar

    steps, importance, _ = study_calendar.plan_inputs(report)
    evidence, overrides = evidence_from_attempts(attempts), overrides or {}
    for concept, found in profile_evidence(profile, now).items():  # this session's own assessed answers win; the profile fills the concepts it has none for
        evidence.setdefault(concept, found)
    for concept, found in lapsed_evidence(profile, now).items():  # lapsed mastery: a short refresh, unless this session has assessed answers of its own
        evidence.setdefault(concept, found)
    adjustments, plan, remediation = [], [], {}
    for step in steps:
        action, factor, reason = decide(step.concept, step.estimated_hours, evidence.get(step.concept))
        original = step.estimated_hours
        adjusted = original
        if action == "compress":
            adjusted = round(min(original, max(MIN_HOURS, original * factor)), 2)
        elif action == "refresh":
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
    for concept in claimed_known(report):  # a subject the learner called known, whose assessed answers say otherwise, comes back as a step (the stored known list is left alone)
        if concept in {s.concept for s in steps} or concept not in evidence or evidence[concept].get("source") == "profile":
            continue
        action, _, reason = decide(concept, 0.0, evidence[concept])
        if action != "remediate":
            continue
        hours = _known_hours(concept)
        overridden = overrides.get(concept) == "reject"
        adjusted = 0.0 if overridden else hours
        remediation[concept] = [] if overridden else _remediation(evidence[concept]["missed"])
        adjustments.append({"concept": concept, "action": "reinstate", "original_hours": 0.0, "adjusted_hours": adjusted, "reason": f"you said you know this, but {reason}".replace("more time is planned", "it is planned again"),
                            "overridden": overridden, "evidence": dict(evidence[concept]), "can_override": True})
        plan.append({"concept": concept, "hours": adjusted, "original_hours": 0.0, "adapted": adjusted != 0.0, "importance": None, "reinstated": True})
    result = {"guarded": guarded(report), "adjustments": adjustments, "plan": plan, "remediation": remediation, "hours_before": round(sum(s.estimated_hours for s in steps), 2), "hours_after": round(sum(p["hours"] for p in plan), 2)}
    if calendar:
        from types import SimpleNamespace

        def schedule(hours_of):
            built = study_calendar.build_calendar([SimpleNamespace(concept=s.concept, estimated_hours=hours_of(s)) for s in steps], importance, calendar["daily_hours"], calendar["today"],
                                                  calendar.get("weekdays"), calendar.get("deadline"))
            return {"finish_date": built["finish_date"], **built["feasibility"]}

        paid = {p["concept"]: p["hours"] for p in plan}
        result["feasibility"] = {"before": schedule(lambda s: s.estimated_hours), "after": schedule(lambda s: paid[s.concept])}
    return result


def claimed_known(report):
    """The subjects the learner reported as already known for this paper (the analysis's missing_prerequisites entries that say so), in report order."""
    from backend.prerequisites.prerequisite_paths import KNOWN_REASON

    return [item["concept"] for item in report.get("missing_prerequisites", []) if item.get("reason") == KNOWN_REASON]


def _known_hours(concept):
    from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner

    return float(PrerequisiteLearningPlanner.STUDY_TIME.get(concept, MIN_HOURS * 2))


def clean_hours(value):
    return isinstance(value, (int, float)) and isfinite(value)


def guarded(report):
    """True when the report's extraction confidence is low and the learner has not confirmed adapting the plan from it anyway."""
    return bool((report.get("confidence_effects") or {}).get("guard_adaptation")) and not report.get("adaptation_confirmed")


def adapted_report(report, attempts, overrides=None, profile=None):
    """The report with its learning_plan hours replaced by the adapted ones (steps carry `adapted: True` and `original_hours`; `adapted_concepts` lists them), so the calendar, plan
    text and curriculum all schedule what the learner's assessed answers call for. Without any adaptation the very same report object is returned, so nothing downstream changes."""
    if guarded(report):  # the extraction is unreliable: no plan change on its own until the learner confirms (POST /adaptive-plan/confirm)
        return report
    proposal = propose(report, attempts, overrides, None, profile)
    changed = {item["concept"]: item["hours"] for item in proposal["plan"] if item["adapted"]}
    reinstated = {item["concept"]: item["hours"] for item in proposal["plan"] if item.get("reinstated") and item["adapted"]}
    if not changed:
        return report
    def adapt(step):
        if step["concept"] not in changed:
            return step
        hours = changed[step["concept"]]
        return {**step, "estimated_hours": hours, "original_hours": step["estimated_hours"], "adapted": True, **({"skipped": True} if hours <= 0 else {})}

    steps = [adapt(step) for step in report.get("learning_plan", [])]
    steps += [{"concept": name, "estimated_hours": hours, "original_hours": 0.0, "adapted": True, "reinstated": True} for name, hours in reinstated.items() if name not in {s["concept"] for s in steps}]
    found = {**report, "learning_plan": steps, "adapted_concepts": sorted(changed)}
    if report.get("math_plan"):
        found["math_plan"] = [adapt(step) for step in report["math_plan"]]
    return found


def session_report(session, adapted=True):
    """The session's report as the schedule should see it: adapted to its assessed answers and the learner's overrides unless `adapted` is False."""
    report = session.report
    return adapted_report(report, getattr(session, "quiz_attempts", []) or [], report.get("adaptive_overrides", {}), profile_quiz(session)) if adapted else report
