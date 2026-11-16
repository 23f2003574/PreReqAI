"""The study plan as it applies to one learner: what the learner's saved knowledge already covers for this paper, what is still outstanding
(most relevant first, each with the reason it is recommended), and how much work is left.

Only reads what the analysis already holds: the prerequisite recommendations and their evidence, the learner's known and studied subjects, the study
plan with its schedule (the one scheduler: days come from paper.study_time), the study hours of PrerequisiteLearningPlanner and the learning paths. It
adds no learner model: `sources` are the names a learner profile supplied, used only to say where a covered subject came from."""
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner
from backend.prerequisites.prerequisite_paths import KNOWN_REASON, build_paths

_STRENGTH = {"strong": 0, "moderate": 1, "weak": 2, "": 3}


def _priority(prerequisite):
    """Most relevant to this paper first: essential before supporting, then strongest evidence in the paper, then the number of the paper's
    concepts that need it, their mentions, and the name so equal evidence always orders the same way."""
    return (0 if prerequisite.importance == "essential" else 1, _STRENGTH.get(prerequisite.evidence_strength, 3), -len(prerequisite.evidence),
            -prerequisite.dependent_mentions, prerequisite.concept)


def build_plan(paper, sources=None):
    """{"covered": [...], "outstanding": [...], "workload": {...}, "path": [...], "sources": {...}} for the paper as it stands now."""
    hours = PrerequisiteLearningPlanner.STUDY_TIME
    sources = {"known": list((sources or {}).get("known", [])), "studied": list((sources or {}).get("studied", []))}
    known = {m.concept for m in getattr(paper, "missing_prerequisites", []) if m.reason == KNOWN_REASON}
    studied = {item.concept for item in getattr(paper, "study_progress", []) if item.completed}
    pending = {item.concept for item in getattr(paper, "study_progress", []) if not item.completed}
    recommended = {p.concept: p for p in paper.prerequisites}
    origin = {name: "your learner profile" for name in (*sources["known"], *sources["studied"])}

    covered = []
    for name in sorted(known | (studied & set(recommended))):
        prerequisite = recommended.get(name)
        covered.append({"concept": name, "status": "known" if name in known else "studied", "from": origin.get(name, "this analysis"),
                        "needed_by": [e["concept"] for e in prerequisite.evidence] if prerequisite else [], "estimated_hours": hours.get(name)})

    outstanding = []
    for number, prerequisite in enumerate(sorted((p for p in paper.prerequisites if p.concept in pending), key=_priority), start=1):
        outstanding.append({
            "priority": number, "concept": prerequisite.concept, "importance": prerequisite.importance, "evidence_strength": prerequisite.evidence_strength,
            "needed_by": [e["concept"] for e in prerequisite.evidence], "estimated_hours": hours.get(prerequisite.concept),
            "why": f"{prerequisite.reason}. {prerequisite.importance_reason} Evidence in the paper: {prerequisite.evidence_strength or 'not graded'}"
                   + (f" ({'; '.join(prerequisite.strength_reasons)})." if prerequisite.strength_reasons else "."),
        })
    remaining = sum(item["estimated_hours"] or 0 for item in outstanding)
    spent = lambda names: sum(hours.get(n, 0) for n in names)
    time = getattr(paper, "study_time", None)
    return {
        "covered": covered, "outstanding": outstanding, "sources": sources,
        "workload": {"without_your_knowledge_hours": spent(recommended), "known_hours": spent(n for n in recommended if n in known),
                     "studied_hours": spent(n for n in recommended if n in studied and n not in known), "remaining_hours": remaining,
                     "remaining_days": getattr(time, "recommended_days", None) if outstanding else 0},
        "path": [step["concept"] for step in build_paths(paper)["combined"]],
    }
