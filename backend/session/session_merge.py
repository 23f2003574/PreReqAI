"""Three-way merge of two versions of one saved session, so that two workers changing it at the same time do not lose each other's updates.

Every save stamps `LearningSession.version`. A worker remembers the facts it last read or wrote (`facts`, the base); when it saves and the file has moved on (a higher
version), the file's session (theirs) and the worker's (ours) are merged against that base:
* sets (studied concepts, dismissed suggestions) keep what both sides kept and everything either side added; a concept one side dropped stays dropped;
* quiz attempts are append-only: theirs, then the attempts ours added after the base; served-but-unanswered questions follow the same add/remove rule;
* concepts marked known change the plan's structure: the side that changed them provides the plan; when both added different ones they are combined; if either side
  also removed one while the other changed too, that is a real conflict: ours wins and the conflict is reported;
* the plan's start is a scalar: the side that changed it wins; both changing it to different dates is a conflict (ours wins, reported).
Everything else comes from the side that provides the plan."""
from types import SimpleNamespace

from backend.session.learning_session import LearningSession


def _known(paper, known_reason):
    return {item.concept for item in getattr(paper, "missing_prerequisites", []) if item.reason == known_reason}


def facts(session: LearningSession) -> dict:
    """What a merge compares: the independently changeable parts of a session."""
    from backend.platform.prereqai_platform import KNOWN_REASON

    paper = session.paper
    return {
        "studied": {item.concept for item in getattr(paper, "study_progress", []) if item.completed},
        "known": _known(paper, KNOWN_REASON) if paper is not None else set(),
        "dismissed": set(getattr(session, "dismissed_suggestions", [])),
        "plan_start": getattr(session, "plan_start", None),
        "attempts": len(getattr(session, "quiz_attempts", [])),
        "pending": set(getattr(session, "quiz_pending", {})),
    }


def _merge_set(base, ours, theirs):
    return (base & ours & theirs) | (ours - base) | (theirs - base)


def merge(ours: LearningSession, theirs: LearningSession, base: dict) -> list[str]:
    """Merge `theirs` (the saved file) with `ours` (this worker's copy) into `ours`, in place; returns the real conflicts found (ours wins each)."""
    from backend.platform import platform
    from backend.platform.prereqai_platform import KNOWN_REASON
    from backend.progress import StudyProgressTracker

    mine, other = facts(ours), facts(theirs)
    conflicts = []
    attempts = [*theirs.quiz_attempts, *ours.quiz_attempts[base["attempts"]:]]
    pending = {key: value for key, value in theirs.quiz_pending.items() if not (key in base["pending"] and key not in mine["pending"])}
    pending.update({key: value for key, value in ours.quiz_pending.items() if key not in base["pending"]})
    dismissed = _merge_set(base["dismissed"], mine["dismissed"], other["dismissed"])
    order = [name for name in [*theirs.dismissed_suggestions, *ours.dismissed_suggestions] if name in dismissed]
    plan_start = mine["plan_start"] if mine["plan_start"] != base["plan_start"] else other["plan_start"]
    if mine["plan_start"] != base["plan_start"] and other["plan_start"] != base["plan_start"] and mine["plan_start"] != other["plan_start"]:
        conflicts.append(f"plan_start: this worker set {mine['plan_start']}, another set {other['plan_start']}")
    mine_changed, theirs_changed = mine["known"] != base["known"], other["known"] != base["known"]
    provider, extra_known = theirs, set()
    if mine_changed and not theirs_changed:
        provider = ours
    elif mine_changed and theirs_changed and mine["known"] != other["known"]:
        if base["known"] <= mine["known"] and base["known"] <= other["known"]:
            extra_known = mine["known"] - other["known"]  # both only added: combine them
        else:
            provider = ours
            conflicts.append(f"known: this worker has {sorted(mine['known'])}, another has {sorted(other['known'])}")
    if provider is ours:
        ours_paper, ours_report = ours.paper, ours.report
    else:
        ours_paper, ours_report = theirs.paper, theirs.report
    studied_now = _merge_set(base["studied"], mine["studied"], other["studied"])
    if provider is not ours:
        for name in ("paper", "report", "active_concept", "current_context", "conversation_history", "learning_gaps", "recommendations", "workflow_memory",
                     "interaction_history", "navigation_history", "last_navigation", "status", "paper_title", "profile"):
            setattr(ours, name, getattr(theirs, name))
    target = SimpleNamespace(paper=ours_paper, report=ours_report)
    if extra_known and ours_paper is not None:
        planned = {item.concept for item in ours_paper.learning_plan}
        platform._personalize(target, sorted(extra_known & planned), sorted(studied_now - extra_known))
    paper = ours.paper
    if paper is not None and getattr(paper, "study_progress", None):
        tracker, changed = StudyProgressTracker(), False
        known_now = _known(paper, KNOWN_REASON)
        for item in paper.study_progress:
            want = item.concept in studied_now and item.concept not in known_now
            if item.completed != want:
                (tracker.complete if want else tracker.reset)(paper, item.concept)
                changed = True
        if changed:
            platform._refresh_progress(paper, ours.report)
    ours.quiz_attempts, ours.quiz_pending = attempts, pending
    ours.dismissed_suggestions, ours.plan_start = list(dict.fromkeys(order)), plan_start
    return conflicts
