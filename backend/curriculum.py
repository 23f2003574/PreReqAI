"""A curriculum over several analysed papers: one deduplicated prerequisite plan, a sensible paper order and one combined schedule.

Each paper's study plan (from its session's report) lists the subjects the learner still has to study. Here those plans are merged: a subject several papers
need appears once, subjects the learner already knows or has studied (in the session, or in the learner profile) are left out, and the remaining work is
laid out once, paper by paper. The next paper is always the one whose still-unscheduled prerequisites cost the fewest extra hours (ties: fewer total hours, then the title, then
the session id), so shared groundwork comes first and cheap papers are not held up by expensive ones; inside a paper the plan's own order (essential subjects first,
never before something they depend on) is kept. The deadline, weekdays and hours per day go through the same calendar as a single paper (study_calendar.py).
Sessions are only read: nothing here changes a session, its report, its quiz history or the profile."""
from copy import deepcopy
from types import SimpleNamespace

from backend import study_calendar
from backend.learner_profile import key, mastered as profile_mastered
from backend.prerequisites.study_time_estimator import schedule_order

MAX_PAPERS = 10


def _paper_view(session, adapted=True):
    """What the curriculum needs of one session: its title, remaining plan steps with importance, and the concepts it already counts as done."""
    report = session.report or {}
    if adapted and report:
        from backend import adaptive_plan

        report = adaptive_plan.session_report(session)  # hours adapted to the paper's assessed answers
    importance = {item["concept"]: item.get("importance") for item in report.get("missing_prerequisites", [])}
    done = {item["concept"] for item in report.get("study_progress", []) if item.get("completed")}
    known = {item["concept"] for item in report.get("missing_prerequisites", []) if str(item.get("reason", "")).startswith("Already known")}
    steps = [SimpleNamespace(concept=step["concept"], estimated_hours=float(step["estimated_hours"])) for step in report.get("learning_plan", [])]
    return {"session_id": session.session_id, "title": (report.get("paper") or {}).get("title") or session.paper_title or session.session_id,
            "steps": steps, "importance": importance, "done": done, "known": known}


def build_curriculum(sessions, profile=None, today=None, deadline=None, hours_per_day=3.0, weekdays=None, accept_mastered=(), adapted=True):
    """The curriculum for `sessions` (LearningSession objects, 1 to MAX_PAPERS) as a plain dict. `profile` is {"known": [...], "studied": [...], "quiz": {...}}
    or None. `today` is a date (required when the calendar is wanted); with it the combined schedule and its feasibility are included. Sessions are not changed."""
    views = [_paper_view(session, adapted) for session in sessions]
    profile = deepcopy(profile) if profile else {"known": [], "studied": [], "quiz": {}}
    mastered = {key(name): ("known in your learner profile" if name in profile["known"] else "studied, according to your learner profile")
                for name in (*profile["known"], *profile["studied"])}
    for view in views:
        for name in view["done"]:
            mastered.setdefault(key(name), f"already studied in the analysis of {view['title']!r}")
    # Quiz mastery kept in the profile is a hint, never a decision: a concept is left out only when the learner names it in `accept_mastered`.
    quiz_mastery = {key(name): info for name, info in profile_mastered(profile.get("quiz", {})).items()}
    for name in accept_mastered:
        if key(name) in quiz_mastery:
            mastered.setdefault(key(name), "you accepted your quiz mastery of it (your learner profile rates it mastered)")
    hours, needed_by, excluded = {}, {}, {}
    separate = 0.0
    for view in views:
        own = [step for step in view["steps"] if step.concept not in view["done"]]
        separate += sum(step.estimated_hours for step in own)
        view["remaining"] = [step for step in own if key(step.concept) not in mastered]
        for step in own:
            hours.setdefault(step.concept, step.estimated_hours)
            if key(step.concept) in mastered:
                excluded.setdefault(step.concept, {"concept": step.concept, "hours_saved": step.estimated_hours, "reason": mastered[key(step.concept)]})
            else:
                needed_by.setdefault(step.concept, []).append(view["title"])
    hints = [{"concept": name, "hours": hours[name], "papers": needed_by[name], "reason": f"your learner profile rates {name} mastered ({quiz_mastery[key(name)]['knew']} of "
             f"{quiz_mastery[key(name)]['attempts']} answers correct over {quiz_mastery[key(name)]['questions']} different questions); it is still in the plan until you accept that"}
             for name in sorted(needed_by) if key(name) in quiz_mastery]
    scheduled, order, papers = set(), [], []
    pending = list(views)
    from backend import paper_citations

    cites = paper_citations.find_links(views, sessions)
    cycle_pairs = {frozenset(pair) for pair in cites["cycles"]}
    needs = {}  # a paper after the papers it cites (cycles are not used)
    for link in cites["links"]:
        if frozenset((link["citing"], link["cited"])) not in cycle_pairs:
            needs.setdefault(link["citing"], []).append(link)
    placed = set()
    while pending:
        def extra(view):
            return sum(step.estimated_hours for step in view["remaining"] if step.concept not in scheduled)

        waiting = {view["session_id"] for view in pending}
        ready = [view for view in pending if not any(link["cited"] in waiting for link in needs.get(view["session_id"], []))] or pending
        pick = min(ready, key=lambda view: (round(extra(view), 6), round(sum(s.estimated_hours for s in view["remaining"]), 6), view["title"], view["session_id"]))
        pending.remove(pick)
        placed.add(pick["session_id"])
        new = [step for step in schedule_order(pick["remaining"], pick["importance"]) if step.concept not in scheduled]
        shared = [step.concept for step in pick["remaining"] if step.concept in scheduled]
        scheduled.update(step.concept for step in new)
        order.extend(new)
        position = len(papers) + 1
        why = [f"Paper {position}: {pick['title']!r} needs {round(sum(s.estimated_hours for s in new), 2)} h of prerequisites not yet scheduled"
               + (f" ({', '.join(step.concept for step in new)})" if new else "")]
        if shared:
            why.append(f"it shares {', '.join(shared)} with the papers before it, so that groundwork is not repeated")
        for link in needs.get(pick["session_id"], []):
            why.append(f"it cites {link['cited_title']!r} (its reference {link['reference_number']}{'' if link['method'] == 'title' else ', matched by ' + link['method'].replace('_', ' ')}), which is placed before it" if link["cited"] in placed else f"it cites {link['cited_title']!r}")
        if not pick["remaining"]:
            why.append("nothing is left to study for it: you can read it now")
        papers.append({"position": position, "session_id": pick["session_id"], "title": pick["title"], "new_prerequisites": [step.concept for step in new],
                       "shared_prerequisites": shared, "cites": [link["cited_title"] for link in needs.get(pick["session_id"], [])], "extra_hours": round(sum(step.estimated_hours for step in new), 2), "reason": "; ".join(why) + "."})
    combined = round(sum(step.estimated_hours for step in order), 2)
    after_mastery = round(sum(step.estimated_hours for view in views for step in view["remaining"]), 2)  # each paper's own plan, less what you know, before sharing
    result = {
        "papers": papers,
        "shared_prerequisites": [{"concept": name, "hours": hours[name], "papers": titles,
                                  "reason": f"{name} is needed by {len(titles)} papers ({'; '.join(titles)}) and is studied once"}
                                 for name, titles in sorted(needed_by.items(), key=lambda item: (-len(item[1]), item[0])) if len(titles) > 1],
        "citations": {**cites, "ordering": [{"paper": link["citing_title"], "after": link["cited_title"], "reference_number": link["reference_number"], "evidence": link["evidence"], "method": link["method"]}
                                              for links in needs.values() for link in links]},
        "shared_references": dict(zip(("references", "totals"), paper_citations.shared_references(sessions))),
        "excluded": sorted(excluded.values(), key=lambda item: item["concept"]),
        "mastery_hints": hints,
        "steps": [{"concept": step.concept, "hours": step.estimated_hours} for step in order],
        "hours": {"separate": round(separate, 2), "after_mastery": after_mastery, "combined": combined, "saved": round(separate - combined, 2),
                  "saved_by_mastery": round(separate - after_mastery, 2), "saved_by_sharing": round(after_mastery - combined, 2)},
    }
    if today is not None:
        result["calendar"] = study_calendar.build_calendar(order, {}, hours_per_day, today, weekdays, deadline)
    return result
