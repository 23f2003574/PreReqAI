"""Ordered, explained learning paths from the concepts of a paper down to their foundations.

Built only from what PreReqAI already has: PrerequisiteDetector.PREREQUISITE_RULES (the one prerequisite table), the paper's study progress and
known subjects, the study hours of PrerequisiteLearningPlanner and the paper's recommended learning resources. No relationship is added here.

Each path lists, foundations first, what one concept of the paper needs: a step is `direct` when the table lists it for the concept and
`transitive` when it is reached through another prerequisite (`chain` shows the way). `combined` merges the paths, each shared prerequisite once
with every concept that needs it, in an order that never places a subject before one it needs. A subject the learner knows or has studied is not a step
(it is listed under `excluded`; what it needs is still shown unless that is known or studied too). A cycle in the table is cut where it closes and
reported, a rule that points at a subject without study hours is reported, and so is a concept of the paper that has no rule. Deterministic:
the table and the paper's concept order decide everything."""
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner

KNOWN_REASON = "Already known (reported by the learner)"


def build_paths(paper, rules=None, hours=None):
    """{"paths": [...], "combined": [...], "excluded": [...], "problems": [...]} for the paper's concepts; see the module docstring."""
    from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

    rules = PrerequisiteDetector.PREREQUISITE_RULES if rules is None else rules
    hours = PrerequisiteLearningPlanner.STUDY_TIME if hours is None else hours
    studied = {item.concept for item in getattr(paper, "study_progress", []) if item.completed}
    known = {item.concept for item in getattr(paper, "missing_prerequisites", []) if item.reason == KNOWN_REASON}
    resources = {item.concept: {"title": item.title, "provider": item.provider, "url": item.url, "estimated_hours": item.estimated_hours}
                 for item in getattr(paper, "learning_resources", [])}
    problems, excluded, seen_problems = [], {}, set()

    def problem(text):
        if text not in seen_problems:
            seen_problems.add(text)
            problems.append(text)

    def walk(root):
        steps, done = [], set()

        def visit(name, chain):
            for child in rules.get(name, []):
                if child in chain:  # a cycle: cut where it closes
                    problem("cycle in the prerequisite table: " + " -> ".join([*chain[chain.index(child):], child]))
                    continue
                if not isinstance(child, str) or not child.strip():
                    problem(f"{name} lists an invalid prerequisite {child!r}")
                    continue
                visit(child, [*chain, child])
                if child in done:
                    continue
                done.add(child)
                if child not in hours:
                    problem(f"{child} (needed by {name}) has no study hours, so it cannot be scheduled")
                if child in known or child in studied:
                    excluded.setdefault(child, "known" if child in known else "studied")
                    continue
                steps.append({"concept": child, "relation": "direct" if child in rules.get(root, []) else "transitive", "needed_by": name,
                              "chain": [root, *chain[1:], child] if chain[1:] else [root, child], "estimated_hours": hours.get(child),
                              "reason": f"{name} needs {child} (PreReqAI's prerequisite table)", "resource": resources.get(child)})

        visit(root, [root])
        return steps

    paths, combined = [], {}
    for concept in getattr(paper, "concepts", []):
        if not rules.get(concept.name):
            if concept.name not in rules:
                problem(f"no prerequisite rule for {concept.name}, so its prerequisites are unknown")
            continue
        steps = walk(concept.name)
        paths.append({"concept": concept.name, "steps": steps})
        for step in steps:
            entry = combined.setdefault(step["concept"], {"concept": step["concept"], "direct_for": [], "transitive_for": [], "estimated_hours": step["estimated_hours"],
                                                         "resource": step["resource"], "reasons": []})
            entry["direct_for" if step["relation"] == "direct" else "transitive_for"].append(concept.name)
            if step["reason"] not in entry["reasons"]:
                entry["reasons"].append(step["reason"])
    ordered = [{**entry, "order": number} for number, entry in enumerate(combined.values(), start=1)]
    return {"paths": paths, "combined": ordered, "excluded": [{"concept": c, "why": why} for c, why in sorted(excluded.items())], "problems": problems}
